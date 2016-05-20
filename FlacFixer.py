import os
import os.path
import argparse
import mutagen.flac


class FlacProps:
    """
    stores properties of a flac file
    """
    def __init__(self, flac_type, base_path):
        self.filename = flac_type.filename
        self.base_path = base_path
        file_stats = os.stat(self.filename)
        self.file_size = file_stats.st_size
        self._id3_headers = None
        self.pic_list = []
        self.pad_list = []
        for block in flac_type.metadata_blocks:
            if block.code == 6:
                self.pic_list.append(len(block.data))
            if block.code == 1:
                self.pad_list.append(block.length)

    def check_id3_header(self):
        """
        Looks for id3v1 and v2 headers in files
        :return: list of found header names (strings)
        """
        fileobj = open(self.filename, 'rb')
        header_type = []
        fileobj.seek(0)
        header = fileobj.read(3)
        if header == b"ID3":
            header_type.append('id3v2')
        fileobj.seek(-128, 2)
        header_v1 = fileobj.read(3)
        if header_v1 == b'TAG':
            header_type.append('id3v1')
        self._id3_headers = header_type


def list_all_files(dirpath):
    """
    create list of all files in dirpath + subfolders
    """
    import_list = []
    for root, dirs, files in os.walk(dirpath):
        for x in files:
            import_list.append(os.path.join(root, x))
    return import_list


def proper_prefix(num, suffix='B'):
    """
    :param num: int.
    :param suffix: unit of choice
    :return: string of size with appropriate prefix
    """
    for prefix in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024:
            return '{:.1f} {}{}'.format(num, prefix, suffix)
        num /= 1024
    return "too big"


def print_per_track(fstats_before, fstats_after):
    """
    :param fstats_before: FlacProps obj
    :param fstats_after:  FlacProps obj
    """
    if fstats_before.filename == fstats_before.base_path:
        print_path = os.path.split(fstats_before.base_path)[1]
    else:
        print_path = os.path.relpath(fstats_before.filename, fstats_before.base_path)
    print('-' * 36)
    print('{} ({})'.format(print_path, proper_prefix(fstats_before.file_size)))
    for header in fstats_before.id3_headers:
        print(' {} tags'.format(header))
    if fstats_before.pad_list:
        for block in fstats_before.pad_list:
            print(' Padding block: {}'.format(proper_prefix(block)))
    else:
        print(' No padding found')
    if fstats_before.pic_list:
        for pic in fstats_before.pic_list:
            print(' Picture: {}'.format(proper_prefix(pic)))
    else:
        print(' No pictures found')
    if fstats_after:  # when 'check only', fstats_after = None
        print()
        if not fstats_after.pic_list:
            if fstats_before.pic_list:
                print(' Pictures succesfully removed')
        else:
            print(' {} pictures remaining'.format(len(fstats_after.pic_list)))
        if sum(fstats_after.pad_list) != sum(fstats_before.pad_list):
            print(' New padding: {}'.format(proper_prefix(sum(fstats_after.pad_list))))
        else:
            print(' Padding was left as found: {}'.format(proper_prefix(sum(fstats_after.pad_list))))
        file_size_reduction = fstats_before.file_size - fstats_after.file_size
        if file_size_reduction:
            print(' File size reduction: {}'.format(proper_prefix(file_size_reduction)))


def print_footer(reduction_list):
    """
    :param reduction_list: list of file size reductions
    """
    total = sum(reduction_list)
    print('-' * 36)
    if len(reduction_list) > 1 and total:
        print()
        print('A total of {} was removed'.format(proper_prefix(total)))


def padding_wrapper(padding_args):
    def padding_rules(y, size=padding_args[0], up=padding_args[1], low=padding_args[2]):
        """
        This function is inserted into mutagen.
        y is a PaddingInfo object which has two attributes:
        y.padding = padding size (better said: amount of unused space between header and audio.
        y.size = size of music content  (not used here)
        """
        if 1024 * low < y.padding < 1024 * up:
            return y.padding
        else:
            return 1024 * size
    return padding_rules


def track_work(file_path, base_path, padding_args, checkonly, keep_id3, keep_pic):
    """
    :param file_path: path of file to be processed
    :param base_path: path that was fed into script
    :param padding_args: tupple of three ints to be passed to padding rules
    :param checkonly: bool
    :param keep_id3: bool
    :param keep_pic: bool
    :return: 2 (or less) FlacProp instances
    """
    try:
        flac = mutagen.flac.FLAC(file_path)
    except mutagen.flac.FLACNoHeaderError:  # file is not flac
        return
    fstats_before = FlacProps(flac, base_path)
    fstats_before.check_id3_header()
    if checkonly:
        return fstats_before, None
    if fstats_before.pic_list and not keep_pic:
        flac.clear_pictures()
    delete_id3 = False
    if fstats_before._id3_headers and not keep_id3:
        delete_id3 = True
    flac.save(padding=padding_wrapper(padding_args), deleteid3=delete_id3)
    flac.load(flac.filename)
    fstats_after = FlacProps(flac, base_path)
    return fstats_before, fstats_after


def main(base_path, pd_sz=8, up_thr=20, lw_thr=4, checkonly=False, silent=False, keepid3=False, keep_pic=False):
    if os.path.isfile(base_path):
        file_list = [base_path]
    elif os.path.isdir(base_path):
        file_list = list_all_files(base_path)
    else:
        raise Exception('{} is not a valid path'.format(base_path))
    reduction_list = []
    for file_path in file_list:
        fstats_before, fstats_after = track_work(file_path, base_path,
                                                 (pd_sz, up_thr, lw_thr), checkonly, keepid3, keep_pic)
        if not silent and fstats_before:  # only flacs have fstats:
            file_size_reduction = fstats_before.file_size - fstats_after.file_size
            reduction_list.append(file_size_reduction)
            print_per_track(fstats_before, fstats_after)
    print_footer(reduction_list)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='FlacFixer romeves pictures and id3 tags from Flac files'
                                                 ' and sets new padding.'
                                                 ' Optionally it can be used for diagnostics alone')
    parser.add_argument("path", metavar='<input path>', help='File or folder to be checked.'
                                                             ' Subfolders are also checked')
    choke_1 = parser.add_mutually_exclusive_group()
    choke_1.add_argument('-s', '--silent', action='store_true', help='no visual output')
    choke_1.add_argument('-c', '--checkonly', action='store_true', help='just show info, file will be unchanged')
    parser.add_argument('-k', '--keep_pic', action='store_true',
                        help='don\'t remove pictures')
    parser.add_argument('-i', '--keepid3', action='store_true',
                        help='don\'t remove id3 tags')
    parser.add_argument('-p', dest='pad_size', metavar='KiB', type=int, default=8,
                        help='Padding size used if existing padding is outside of thresholds. Default = 8')
    parser.add_argument('-u', dest='upper', metavar='KiB', type=int, default=20,
                        help='Padding is left same size when between upper and lower threshholds.'
                             ' Upper default = 20')
    parser.add_argument('-l', dest='lower', metavar='KiB', type=int, default=4,
                        help='Lower threshold. Default = 4')

    args = parser.parse_args()
    main(args.path, args.pad_size, args.upper, args.lower, args.checkonly, args.silent, args.keepid3, args.keep_pic)


# # path = 'D:\Artist - Album (Year) FLAC\Subfolder\\03. 1 picture 3 padding.flac'
# # path = "D:\Artist - Album (Year) FLAC"
# path = "E:\\test\\aa fixer\Various - Only for the Headstrong Vol. II (flac)"
#
# main(path, checkonly=True)
