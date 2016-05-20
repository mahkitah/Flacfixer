import os
import os.path
import argparse
import mutagen.flac


class FlacProps:
    """
    stores properties of a flac file
    """
    def __init__(self, flac_type, base_path):
        self.id3_headers = None
        self.filename = flac_type.filename
        if self.filename == base_path:  # input is single file
            self.print_path = os.path.split(base_path)[1]
        else:
            self.print_path = os.path.relpath(self.filename, base_path)
        file_stats = os.stat(self.filename)
        self.file_size = file_stats.st_size
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
        self.id3_headers = header_type


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
    :param num: integer
    :param suffix: unit of choice
    :return: string of size with appropriate prefix
    """
    for prefix in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024:
            return '{:.1f} {}{}'.format(num, prefix, suffix)
        num /= 1024
    return "too big"


def print_per_track(track_info):
    """
    :param track_info: tupple with FlacProps objects
    :return: int. - file size reduction
    """
    st_before = track_info[0]
    st_after = track_info[1]
    print('-' * 36)
    print('{} ({})'.format(st_before.print_path, proper_prefix(st_before.file_size)))
    for header in st_before.id3_headers:
        print(' {} tags'.format(header))
    if st_before.pad_list:
        for block in st_before.pad_list:
            print(' Padding block: {}'.format(proper_prefix(block)))
    else:
        print(' No padding found')
    if st_before.pic_list:
        for pic in st_before.pic_list:
            print(' Picture: {}'.format(proper_prefix(pic)))
    else:
        print(' No pictures found')
    if st_after:  # when 'check only', st_after = None
        print()
        if not st_after.pic_list:
            if st_before.pic_list:
                print(' Pictures succesfully removed')
        else:
            print(' {} pictures remaining'.format(len(st_after.pic_list)))
        if sum(st_after.pad_list) != sum(st_before.pad_list):
            print(' New padding: {}'.format(proper_prefix(sum(st_after.pad_list))))
        else:
            print(' Padding was left as found: {}'.format(proper_prefix(sum(st_after.pad_list))))
        file_size_reduction = st_before.file_size - st_after.file_size
        if file_size_reduction:
            print(' File size reduction: {}'.format(proper_prefix(file_size_reduction)))
        return file_size_reduction
    return 0


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
        y.padding = padding size
        y.size = size of music content  (not used here)
        """
        if 1024 * low < y.padding < 1024 * up:
            return y.padding
        else:
            return 1024 * size

    return padding_rules


def track_work(file_path, base_path, padding_args, checkonly, keep_id3):
    """
    :param file_path: path of file to be processed
    :param base_path: path that was fed into script
    :param padding_args: tupple of three ints to be passed to padding rules
    :param checkonly: bool
    :param keep_id3: bool
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
    if fstats_before.pic_list:
        flac.clear_pictures()
    delete_id3 = False
    if fstats_before.id3_headers and not keep_id3:
        delete_id3 = True
    flac.save(padding=padding_wrapper(padding_args), deleteid3=delete_id3)
    flac.load(flac.filename)
    fstats_after = FlacProps(flac, base_path)
    return fstats_before, fstats_after


def main(base_path, pd_sz=8, up_thr=20, lw_thr=4, checkonly=False, silent=False, keepid3=False):
    if os.path.isfile(base_path):
        file_list = [base_path]
    elif os.path.isdir(base_path):
        file_list = list_all_files(base_path)
    else:
        raise Exception('{} is not a valid path'.format(base_path))
    reduction_list = []
    for file_path in file_list:
        track_info = track_work(file_path, base_path, (pd_sz, up_thr, lw_thr), checkonly, keepid3)
        if not silent and track_info:  # only flacs have track_info:
            reduction_list.append(print_per_track(track_info))
    print_footer(reduction_list)


# if __name__ == "__main__":
#     parser = argparse.ArgumentParser()
#     parser.add_argument("path", help='file- or directory path')
#     choke_1 = parser.add_mutually_exclusive_group()
#     choke_1.add_argument('-s', '--silent', help='no output', action='store_true')
#     choke_1.add_argument('-c', '--checkonly', help='just show info, file will be unchanged', action='store_true')
#     parser.add_argument('-i', '--keepid3',
#                         help='don\'t remove id3 tags', action='store_true')
#     parser.add_argument('-p', '--pad_size', type=int, default=8,
#                         help='Padding size used if existing padding is outside of thresholds. Default = 8 (KiB)')
#     parser.add_argument('-u', '--upper', type=int, default=20,
#                         help='Padding is left same size when between upper and lower threshholds.'
#                              ' Upper default = 20 (KiB)')
#     parser.add_argument('-l', '--lower', type=int, default=4,
#                         help='Lower threshold. Default = 4 (KiB)')
#
#     args = parser.parse_args()
#     main(args.path, args.pad_size, args.upper, args.lower, args.checkonly, args.silent, args.keepid3)


# # path = 'D:\Artist - Album (Year) FLAC\Subfolder\\03. 1 picture 3 padding.flac'
# # path = "D:\Artist - Album (Year) FLAC"
# path = "E:\\test\\aa fixer\Various - Only for the Headstrong Vol. II (flac)"
#
# main(path, checkonly=True)
