import os
import os.path
import argparse
import mutagen.flac
import hashlib
from collections import OrderedDict


class FlacProps:
    """
    stores properties of a flac obj
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
                self.pic_list.append((len(block.data), block.width, block.height))
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


def list_all_files(input_paths):
    """
    create list of all files in dirpath + subfolders
    """
    rough_list = []
    if isinstance(input_paths, str):  # allows for string input when used as a module
        input_paths = [input_paths]
    for path in input_paths:
        if os.path.isfile(path):
            rough_list.append(path)
        elif os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                for x in files:
                    rough_list.append(os.path.join(root, x))
    if not rough_list:
        raise Exception('No valid path entered')
    clean_list = list(OrderedDict.fromkeys(rough_list))  # removes dupes while keeping order
    common_path = os.path.commonpath(clean_list)

    return clean_list, common_path


def get_md5(data):
    hash_obj = hashlib.md5(data)
    return hash_obj.digest()


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


def print_if_true(test, txt):
    if test:
        print(txt)


def print_check(fstats_before):

    if fstats_before.filename == fstats_before.base_path:
        print_path = os.path.split(fstats_before.base_path)[1]
    else:
        print_path = os.path.relpath(fstats_before.filename, fstats_before.base_path)
    print('-' * 36)
    print('{} ({})'.format(print_path, proper_prefix(fstats_before.file_size)))
    for header in fstats_before._id3_headers:
        print(' {} tags'.format(header))
    if fstats_before.pic_list:
        for pic in fstats_before.pic_list:
            print(' Picture ({} x {}) {}'.format(pic[1], pic[2], proper_prefix(pic[0])))
    else:
        print(' No pictures found')
    if fstats_before.pad_list:
        for block in fstats_before.pad_list:
            print(' Padding block: {}'.format(proper_prefix(block)))
    else:
        print(' No padding found')


def print_results(track_info):
    """
    :type track_info: tuple of two FlacProp instances
    """
    fstats_before, fstats_after = track_info
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
    file_size_change = fstats_after.file_size - fstats_before.file_size
    print_if_true(file_size_change < 0, ' File size reduction: {}'.format(proper_prefix(abs(file_size_change))))
    print_if_true(file_size_change > 0, ' File size increase: {}'.format(proper_prefix(file_size_change)))


def print_footer(ind_changes_list):
    """
    :param ind_changes_list: list
    """
    total_min = sum([abs(x) for x in ind_changes_list if x < 0])
    total_plus = sum([x for x in ind_changes_list if x > 0])
    print('-' * 36)
    if len(ind_changes_list) > 1:
        print()
        print_if_true(total_min, 'A total of {} was removed'.format(proper_prefix(total_min)))
        print_if_true(total_plus, 'A total of {} was added'.format(proper_prefix(total_plus)))


def padding_wrapper(padding_args):
    def padding_rules(y, size=padding_args[0], up=padding_args[1], low=padding_args[2]):
        """
        This function is inserted into mutagen.
        y is a PaddingInfo object which has two attributes:
        y.padding = padding size (better said: amount of unused space between header and audio.
        y.size = size of music content  (not used here)
        """
        if 1024 * low <= y.padding <= 1024 * up:
            return y.padding
        else:
            return 1024 * size
    return padding_rules


def make_save_path(mime, flac_filename, loc_list):
    """
    :param mime: str.
    :param flac_filename: str.
    :param loc_list: list of used picture save locations
    """
    try:
        extension = mime.split('/')[1].replace('jpeg', 'jpg')
    except IndexError:
        extension = 'pic'
    location = os.path.dirname(flac_filename)
    count = loc_list.count(location) + 1
    loc_list.append(location)
    save_path = os.path.join(location, 'cover{}.{}'.format(count, extension)).replace('cover1.', 'cover.')
    while os.path.isfile(save_path):
        loc_list.append(location)
        count += 1
        save_path = os.path.join(location, 'cover{}.{}'.format(count, extension))
    return save_path


def save_pictures(flac, saved_pics, loc_list):
    """
    :param flac: mutagen Flac obj.
    :param saved_pics: set of tupples: {(size, checksum), ...}
    :param loc_list: list of used pic. save locations
    """
    for pic_obj in flac.pictures:
        checksum = get_md5(pic_obj.data)
        if checksum in saved_pics:
            pass
        else:
            saved_pics.add(checksum)
            save_path = make_save_path(pic_obj.mime, flac.filename, loc_list)
            with open(save_path, 'wb') as new_file:
                new_file.write(pic_obj.data)


def track_work(file_path, base_path, padding_args, checkonly, keep_id3, keep_pic, pic_save, saved_pics, loc_list):
    """
    :param file_path: str. file to be processed
    :param base_path: str. path that fed into the script
    :param padding_args: tupple of 3 padding settings
    :param keep_pic: bool.
    :param keep_id3: bool.
    :param checkonly: bool.
    :param checkonly, silent, keep_id3, keep_pic, pic_save: bool.
    :param saved_pics: set of tupples: {(size, checksum), ...}
    :param loc_list: list of used pic. save locations
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
        if pic_save:
            save_pictures(flac, saved_pics, loc_list)
        if not keep_pic:
            flac.clear_pictures()
    delete_id3 = False
    if fstats_before._id3_headers and not keep_id3:
        delete_id3 = True
    flac.save(padding=padding_wrapper(padding_args), deleteid3=delete_id3)
    flac.load(flac.filename)
    fstats_after = FlacProps(flac, base_path)
    return fstats_before, fstats_after


def main(input_path, pd_sz=8, up_thr=20, lw_thr=4,
         checkonly=False, silent=False, keepid3=False, keep_pic=False, pic_save=False):
    """
    :param input_path: str. or list of strings
    :param pd_sz: int.
    :param up_thr: int.
    :param lw_thr: int.
    :param checkonly: bool.
    :param silent: bool.
    :param keepid3: bool.
    :param keep_pic: bool.
    :param pic_save: bool.
    :return: nothing
    """
    work_list, base_path = list_all_files(input_path)
    ind_change_list = []
    saved_pics = set()
    loc_list = []

    for file_path in work_list:
        track_info = track_work(file_path, base_path, (pd_sz, up_thr, lw_thr),
                                checkonly, keepid3, keep_pic, pic_save, saved_pics, loc_list)
        if not track_info:  # non flacs
            continue
        if not checkonly:
            ind_change_list.append(track_info[1].file_size - track_info[0].file_size)
        if not silent:
            print_check(track_info[0])
            if not checkonly:
                print_results(track_info)

    if not silent:
        print_footer(ind_change_list)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='FlacFixer removes pictures and id3 tags from Flac files'
                                                 ' and sets new padding.'
                                                 ' Optionally it can be used for diagnostics alone')
    parser.add_argument("path", nargs='+', metavar='<input path>',
                        help='File or folder to be checked. Subfolders are also checked')
    choke_1 = parser.add_mutually_exclusive_group()
    choke_1.add_argument('-s', '--silent', action='store_true', help='No visual output')
    choke_1.add_argument('-c', '--checkonly', action='store_true', help='Just show info, file will be unchanged')
    parser.add_argument('-d', '--pics2disc', action='store_true', help='Save pics to disc. '
                                                                       '(duplicates will not be saved)')
    parser.add_argument('-k', '--keep_pic', action='store_true',
                        help='Don\'t remove pictures')
    parser.add_argument('-i', '--keepid3', action='store_true',
                        help='Don\'t remove id3 tags')
    parser.add_argument('-p', dest='pad_size', metavar='KiB', type=int, default=8,
                        help='Padding size used if existing padding is outside of thresholds. Default = 8')
    parser.add_argument('-u', dest='upper', metavar='KiB', type=int, default=20,
                        help='Padding is left same size when between upper and lower threshholds.'
                             ' Upper default = 20')
    parser.add_argument('-l', dest='lower', metavar='KiB', type=int, default=4,
                        help='Lower threshold. Default = 4')

    args = parser.parse_args()
    main(args.path, args.pad_size, args.upper, args.lower, args.checkonly,
         args.silent, args.keepid3, args.keep_pic, args.pics2disc)
