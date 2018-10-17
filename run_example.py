#!/usr/bin/python
# -*- coding: utf-8 -*-

from imgdownloader.imgdownloader import *
from imgdownloader.urlsextractor import *


def main():
    """ This is example script which based on the given text file with URLs downloads images """
    img_urls_path = ""

    print('Please specify the path to the file with URLs to images to download:')
    try:
        img_urls_path = str(input(""))
    except ValueError as e:
        print("Wrong path is given")
        sys.exit(1)

    print('Please specify output directory:')
    try:
        dir_out = str(input(""))
    except ValueError as e:
        # use default output directory
        dir_out = "./output"
        pass

    def log(err_text):
        print(err_text)

    # extract image urls from the file
    urls = get_urls(img_urls_path, logger_func=log)

    dwnldr = ImgDownloader(threads_max=8)

    # start downloading
    dwnldr.download(dir_out, False, *urls)

    # define callback function
    def dwnld_completed(dwnld_info):
        print("Image with url=%s was completed. It has state=\"%s\" and path=\"%s\"" %
              (dwnld_info.url, dwnld_info.state, dwnld_info.path))

    # wait untill everything is downloaded
    dwnldr.wait_until_downloaded(dwnld_completed)


if __name__ == '__main__':
    main()
