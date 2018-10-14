import os
import time
import requests
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from collections import namedtuple


class ImgDownloadState(Enum):
    """
    Image download states during download process.
    """
    PENDING = 0
    """ download is not started yet """
    RUNNING = 1,
    """ download is in progress """
    CANCELLED = 2,
    """ download is cancelled """
    CANCELLED_ERROR = 3,
    """ download is cancelled because of error """
    FINISHED = 4,
    """ download is finished """

    @classmethod
    def has_item(cls, state):
        """
        Checks if value is a part of this Enum.

        :param state: value which should be checked whether it is a part of this Enum.
        :return: True in case passed value is a part of this Enum. False otherwise.
        """
        return any(state == item for item in cls)


ImgDownloadInfo = namedtuple('ImgDownloadInfo', 'url path state exception')
"""
Information about the downloading image

:param url: url of the image
:param path: path path to the image
:param state: current download stat of the image. Please see @ImgDownloadState
:param exception: exception which occurred downloading, or None in case nothing happened
"""


class ImgDownloader:
    class _ImgItem:
        def __init__(self, url, dir_out):
            """
            Information about the downloading image.

            :param url: url of the image
            :param dir_out: dir_out desired output image directory
            """
            self.url = url
            self.dir_out = dir_out

            # make sure that the passed output directory has correct ending
            if self.dir_out[-1] != '/':
                self.dir_out += '/'

            self.name = None  # name of the image
            self.exception = None  # stores exception occured during downloading
            self.is_user_cancelled = False  # flags which identifies if the download task was cancelled by user
            self.is_sent_to_obsrvr = False  # flag to identify whether the information from this
            # item has been already sent to the observer or not.

        def get_path(self):
            img_path = None
            if self.name is not None:
                img_path = self.dir_out + self.name
            return img_path

    DOWNLOAD_FAIL_MAX = 10
    """
    Maximum number of retries to download image in case of some errors.
    
    ATTENTION: Don't make this value too big! There is a worst case scenario when all threads will be blocked
    e.g. by retrying to use invalid link. If functionality for retrying to download image e.g. every 1 hour is needed,
    thread scheduler has to be implemented with adding different priorities to images (based on the attempts to
    download this image) 
    """

    DOWNLOAD_FAIL_RETRY_T = 0.5
    """ Time to wait in seconds between retrying to download again.
    
    ATTENTION: Don't make this time too big! There is a worst case scenario when all threads will be blocked
    e.g. by retrying to use invalid link. If functionality for retrying to download image e.g. every 1 hour is needed,
    thread scheduler has to be implemented with adding different priorities to images (based on the attempts to
    download this image) """

    def __init__(self, threads_max=8):
        """
        This class is responsible for downloading images from internet. It provides various methods for performing
        different download operations (e.g. download, cancel, remove, restart operations). It also allows a caller to
        follow the download process by acquiring the information about downloading images in real time.
        Each download task is run in the separate thread, therefore download process doesn't block the caller
        (until @wait_until_downloaded method is called).
        Download process is fault tolerant: in case of lost connection or some other errors it
        retries to continue downloading several times and after that starts another download task.

        :param threads_max: maximum number of threads which can run and execute download tasks at the same time.
        """
        if threads_max <= 0:
            raise ValueError("threads_max has to be greater than 0")

        self._tpool = ThreadPoolExecutor(threads_max)  # Thread executing pool containing threads executing download tasks
        self._dwnlds = {}  # dictionary with all download tasks.
        # Each dictionary item has format of the tuple: ('url' : (_ImgItem object, Future object))

######################################## PRIVATE FUNCTION DEFINITIONS #################################################

    def _update_img_name(self, img_item, do_rewrite):
        """
        Extract the name of the image from URL, and assign to the passed img_item.

        :param img_item:
        :param do_rewrite:
        """

        # extract image name from the url
        img_name_full = img_item.url.split('/')[-1]

        # split image name for extension and name itself
        extension = os.path.splitext(img_name_full)[1]
        img_name = os.path.splitext(img_name_full)[0]

        img_path = img_item.dir_out + img_name
        postfix = ""

        if not os.path.exists(img_item.dir_out):
            # create output directory as it doesn't exist
            os.makedirs(img_item.dir_out)
            # if no directory exists, we can be sure, that file with the specified name also doesn't exist there
        elif not do_rewrite:
            # in case image with the specified name already exists in output folder - add unique postfix to the name
            n = 1
            while os.path.isfile(img_path + postfix + extension):
                n += 1
                postfix = "_" + str(n)

        # set final image name
        img_item.name = img_name + postfix + extension

    def _download_img(self, img_item, do_rewrite):
        """
        Download the image from internet based on the passed URL. This function is executed in the separate thread.

        :param img_item: _img_item object with the information used for downloading (e.g. url, output directory)
        :param do_rewrite: in case True and image with the downloading name already exists in the output directory,
        the existing image will be owerwritten with the downloading image.
        :return: img_item
        """
        img_item.is_sent_to_obsrvr = False  # reset flag as after each download we should notify observer again
        if (img_item.name is not None) and do_rewrite:
            # in case we are restarting download - rewrite already existing image
            pass
        else:
            # update name of the image
            self._update_img_name(img_item, do_rewrite)

        # start downloading
        fail_cnt = 0
        is_downloading = True
        while is_downloading:
            try:
                """try to retrieve the image as a stream (without storing everything in the memory, 
                but storing only small chunks). """
                response = requests.get(img_item.url, stream=True, timeout=10)
                if response.status_code == requests.codes.ok:
                    # start writing chunks of data into the file
                    with open(img_item.get_path(), 'wb') as img_f:
                        for chunk in response.iter_content(chunk_size=512):
                            if img_item.is_user_cancelled:
                                # exit the task - user has cancelled the download
                                break
                            if chunk:
                                img_f.write(chunk)

                    # download is finished
                    is_downloading = False
                else:
                    # response is not OK (most probably URL is not correct), raise status exception
                    response.raise_for_status()
            except Exception as e:
                # some exception occurred during retrieving the image (e.g. wrong URL or connection is lost)
                if img_item.is_user_cancelled:
                    # exit the task - user has cancelled the download
                    is_downloading = False
                else:
                    if fail_cnt < ImgDownloader.DOWNLOAD_FAIL_MAX:
                        fail_cnt += 1
                        # try to download image again after some time
                        time.sleep(ImgDownloader.DOWNLOAD_FAIL_RETRY_T)
                    else:
                        # store exception and let the caller decide what to do with this exception
                        img_item.exception = e
                        is_downloading = False

        return img_item

    def _get_download_state(self, img_item, future):
        """
        See @get_download_state description.

        Return @ImgDownloadingState based on the state of img_item and future objects.

        :param img_item: _ImgItem object which is used to identify current download state of the image URL
        stored inside this object
        :param future: Future object which is used to identify current download state of the image URL
        stored inside _ImgItem object
        :return: @ImgDownloadingState related to the downloading image from URL specified inside _ImgItem object
        """
        state = ImgDownloadState.PENDING
        if future.cancelled():
            state = ImgDownloadState.CANCELLED
            if future.exception is not None:
                # during thread execution some unhandled exception occurred
                state = ImgDownloadState.CANCELLED_ERROR
        elif future.done():
            state = ImgDownloadState.FINISHED
            if img_item.exception is not None:
                # during image download some exception occurred
                state = ImgDownloadState.CANCELLED_ERROR
            elif img_item.is_user_cancelled:
                # user cancelled the download task
                state = ImgDownloadState.CANCELLED
        elif future.running():
            state = ImgDownloadState.RUNNING
        else:
            pass
        return state

    def _get_download_info(self, img_item, future):
        """
        See @get_download_info description.

        :param img_item:
        :param future:
        :return:
        """

        state = self._get_download_state(img_item, future)

        return ImgDownloadInfo(img_item.url, img_item.get_path(), state, img_item.exception)

    def _cancel(self, img_item, future):
        """
        See @cancel description.

        :param img_item:
        :param future:
        :return:
        """

        # try to cancel a future (it will work only if future is not in the running state)
        future.cancel()
        # change img_item state to cancelled by user state - it will cancel the running futures
        img_item.is_user_cancelled = True
        future.result()

    def _submit(self, img_item, do_rewrite):
        img_item.is_user_cancelled = False
        future = self._tpool.submit(self._download_img, img_item, do_rewrite)
        self._dwnlds[img_item.url] = (img_item, future)

######################################## PUBLIC FUNCTION DEFINITIONS #################################################

    @property
    def imgs_done(self):
        """ Number of download tasks which were done with FINISHED/CANCELLED/CANCELLED_ERROR states.

        :return: total amount of the done download tasks
        """
        return len(self.get_download_infos_by_state(ImgDownloadState.FINISHED,
                                                    ImgDownloadState.CANCELLED,
                                                    ImgDownloadState.CANCELLED_ERROR))

    @property
    def imgs_total(self):
        """ Total amount of download tasks with all possible states.

        :return: total amount of the images added for downloading.
        """
        return len(self._dwnlds)

    def download(self, dir_out, do_rewrite=False, *urls):
        """
        Download images from internet based on the specified URLs and store them into the specified directory.
        Each download task is executed in separate thread.
        If download task with the specified URL already exists - download will not be started.
        If you want to add another download task with the already existing url, you first must @remove the download task
        or use @restart method.
        After this method is called for each url one download task is created. You can follow each download task
        by acquiring @ImgDownloadInfo object via calling @get_download_info method.
        If you want to wait until all download threads are done, please call @wait_until_downloaded method.
        """

        for url in urls:
            if url in self._dwnlds:
                """ specified url already exists - do nothing """
                pass
            else:
                img_item = self._ImgItem(url, dir_out)
                # create download task
                self._submit(img_item, do_rewrite)

    def wait_until_downloaded(self, done_callback=None):
        """
        Wait until all download tasks are completed. In case callback function is provided by the observer,
        observer will be notified about each completed download task (in case this task was not sent already before).
        After the execution of this function is finished, all existing download tasks are marked as "sent to observer".
        It means that with the next call of this function, the observer will not be notified with the information
        about these download tasks. The information about already completed and not yet sent download tasks is sent
        to the observer first.

        :param done_callback: callback function which will be called every time
        after the information about completed and not yet sent download task is available.
        The callback is called with a single argument - the ImgDownloadInfo object
        :type done_callback: callbackFunction(ImgDownloadInfo)
        """
        futures = [future for (img_item, future) in self._dwnlds.values()]
        for f_complete in concurrent.futures.as_completed(futures):
            img_item = None
            try:
                img_item = f_complete.result()
            except Exception as e:
                """ map future to img_item. We expect that exception is rare 
                case and therefore it is ok to perform linear search """
                img_items = [img_item for (img_item, f) in self._dwnlds.values() if f == f_complete]
                if len(img_items) != 1:
                    # we expect only one future is found in dictionary
                    raise RuntimeError("Wrong Implementation")

                img_item = img_items[0]

            if (done_callback is not None) and (not img_item.is_sent_to_obsrvr):
                done_callback(self._get_download_info(img_item, f_complete))

            img_item.is_sent_to_obsrvr = True

    def remove(self, *urls):
        """
        Cancels and removes existing download tasks based on the specified urls.

        :param url: URLs used to find download tasks to remove
        """
        for url in urls:
            dwnld = self._dwnlds.pop(url, None)
            if dwnld is not None:
                (img_item, future) = dwnld
                self._cancel(img_item, future)

    def cancel(self, *urls):
        """
        Cancels existing download tasks based on the specified urls.

        :param url: URLs used to find download tasks to cancel
        """
        for url in urls:
            if url in self._dwnlds:
                (img_item, future) = self._dwnlds[url]
                self._cancel(img_item, future)

    def restart(self, *urls):
        """
        Restarts already existing download tasks. Already running download tasks will be cancelled,
        and then started again.

        :param urls: URLs used to find download tasks to restart.
        """
        for url in urls:
            if url in self._dwnlds:
                self.cancel(url)
                (img_item, future) = self._dwnlds[url]
                self._submit(img_item, True)

    def get_urls(self):
        """
        Returns all available URLs assigned to the download tasks.

        :return: all available URLs assigned to the download tasks.
        """
        return [img_item.url for (img_item, f) in self._dwnlds.values()]

    def get_download_info(self, url):
        """
        Get download info about download task based on the specified url.

        :param url: URL used to find download task.
        :return: @ImgDownloadInfo object for the specified URL
        """
        dwnld_info = None
        if url in self._dwnlds:
            (img_item, future) = self._dwnlds[url]
            dwnld_info = self._get_download_info(img_item, future)

        return dwnld_info

    def get_download_state(self, url):
        """
        Return download state of the download task based on the specified URL.

        :param url: URL used to find download task.
        :return: download state of the download task based on the specified URL.
        """
        state = None
        if url in self._dwnlds:
            (img, future) = self._dwnlds[url]
            state = self._get_download_state(img, future)

        return state

    def get_download_infos_by_state(self, *states):
        """
        Return @ImgDownloadInfo objects related to the download tasks with the specified download states.

        :param states: download states used for searching the desired download tasks.
        :return: list of the @ImgDownloadInfo objects related to the download tasks with the specified download states.
        """
        for state in states:
            if not ImgDownloadState.has_item(state):
                raise ValueError("state value should be a type of ImgDownloadState")

        # find download tasks with the specified state
        dwnlds = [(img_item, f) for (img_item, f) in self._dwnlds.values()
                  if self._get_download_state(img_item, f) in states]

        # acquire and return download infos for the found download tasks
        dwnld_infos = [self._get_download_info(img_item, f) for (img_item,f) in dwnlds]

        return dwnld_infos