ImgDownloader
=========

A package for downloading images.

ImgDownloader requires Python 3.4 or newer, ``responses`` 0.9.0 or newer and ``requests`` 2.19.1 or newer.


Installing
----------
All external packages and its versions are listed in ``requirements.txt`` and can be installed with pip:

``pip install -r requirements.txt``

To install ``ImgDownloader`` itself please execute:

``python setup.py install``

Usage guide
------
This package allows to download images from internet.

..  code-block:: python

    from imgdownloader.imgdownloader import *
    from imgdownloader.urlsextractor import *

    def log(err_text):
        print(err_text)

    # extract image urls from the file
    urls = get_urls("img_urls.txt", logger_func=log)

    dwnldr = ImgDownloader()

    # start downloading
    dwnldr.download("./output", False, *urls)

    # wait untill everything is downloaded
    dwnldr.wait_until_downloaded()

``ImgDownloader`` provides various methods for performing different download operations (e.g. download, cancel, remove,
restart operations). Each download task is run in the separate thread, therefore download process doesn't block the caller
(until ``wait_until_downloaded`` method is called).

..  code-block:: python

    from imgdownloader.imgdownloader import *
    import time

    urls = ["https://habrastorage.org/webt/y0/nc/6i//y0nc6ianhueuc3tqnwkn5qbl0h4.jpeg",
            "https://habrastorage.org/webt/54/1e/jo/541ejotttsu8hl3swtihly-liro.png",
            "some_wrong_url.png"]

    dwnldr = ImgDownloader(threads_max=2)

    # start downloading
    dwnldr.download("./output", False, *urls)

    # cancel first URL
    dwnldr.cancel(urls[0])

    # restart first URL
    dwnldr.restart(urls[0])

    while (dwnldr.imgs_done < len(urls)):
        # do some stuff until all images are downloaded
        print("Still downloading")
        time.sleep(0.1)

    # make sure that no errors occured during downloading
    for dwnld_info in dwnldr.get_download_infos_by_state(ImgDownloadState.CANCELLED_ERROR):
        print("Image with url=%s was not downloaded. The following exception occured=\"%s\"" % (
        dwnld_info.url, dwnld_info.exception))

    # print information about successfully downloaded images
    for dwnld_info in dwnldr.get_download_infos_by_state(ImgDownloadState.FINISHED):
        print("Image with url=%s was downloaded successfully and stored under \"%s\"" % (dwnld_info.url, dwnld_info.path))

    # remove all information about download tasks from the downloader
    dwnldr.remove(*urls)


You can also wait until all download tasks are finished, and be notified after each of this task is finished.

..  code-block:: python

    from imgdownloader.imgdownloader import *
    from imgdownloader.urlsextractor import *

    def log(err_text):
        print(err_text)

    # extract image urls from the file
    urls = get_urls("img_urls.txt", logger_func=log)

    dwnldr = ImgDownloader(threads_max=8)

    # start downloading
    dwnldr.download("./output", False, *urls)

    # define callback function
    def dwnld_completed(dwnld_info):
        print("Image with url=%s was completed. It has state=\"%s\" and path=\"%s\"" %
              (dwnld_info.url, dwnld_info.state, dwnld_info.path))

    # wait untill everything is downloaded
    dwnldr.wait_until_downloaded(dwnld_completed)

The download process is fault tolerant: in case of lost connection or some other errors it
retries to continue downloading several times and after that starts another download task.

Running tests
------
To run unit tests please go to the root folder of the package and execute:

``python -m unittest discover -v``

