import unittest
import shutil
import os
import time
import responses
from unittest.mock import patch

from imgdownloader.imgdownloader import *

url_wrong = "https://not.exist.com/wrong.png"

img_jpeg_correct = "y0nc6ianhueuc3tqnwkn5qbl0h4.jpeg"
url_jpeg_correct = "https://habrastorage.org/webt/y0/nc/6i/" + img_jpeg_correct

img_png_correct = "541ejotttsu8hl3swtihly-liro.png"
url_png_correct = "https://habrastorage.org/webt/54/1e/jo/" + img_png_correct

img_jpg_correct = "fbd8c69158dc31ae76206418b3e48198.jpg"
url_jpg_correct = "https://habrastorage.org/getpro/habr/post_images/fbd/8c6/915/" + img_jpg_correct

sites_imgs_correct = [("https://habrastorage.org/webt/y0/nc/6i/", img_jpeg_correct, "jpeg"),
                      ("https://habrastorage.org/webt/54/1e/jo/", img_png_correct, "png"),
                      ("https://habrastorage.org/getpro/habr/post_images/fbd/8c6/915/", img_jpg_correct, "jpg")]

urls_correct = [site+img_name for (site, img_name, extension) in sites_imgs_correct]

dir_out = "./output/"

threads_max = 2


def _delete_output(path):
    # try to remove the output directory with all files inside
    if os.path.exists(path):
        # print("Deleting output directory")
        shutil.rmtree(path, ignore_errors=True)
        t = 0
        # wait max 5 seconds until directory is deleted
        while os.path.exists(path) and t < 5:  # check if it exists
            t += 0.5
            time.sleep(0.5)


class TestDownloads(unittest.TestCase):
    def _mock_responses(self):
        for (site, img_name, extension) in sites_imgs_correct:
            with open('tests/support/images/' + img_name, 'rb') as img_file:
                responses.add(
                    responses.GET, site + img_name,
                    body=img_file.read(), status=200,
                    content_type='image/' + extension,
                    stream=True
                )

        responses.add(
            responses.GET, url_wrong,
            json={'error': 'not found'}, status=404
        )

    def _check_if_downloaded(self, dwnldr, dwnlds_expect, state_expect, *urls):
        # check the number of finished tasks
        self.assertEqual(dwnldr.imgs_total, dwnlds_expect)
        self.assertEqual(dwnldr.imgs_done, dwnlds_expect)

        # check that image is really downloaded
        for url in urls:
            dwnld_info = dwnldr.get_download_info(url)
            self.assertTrue(os.path.exists(dwnld_info.path))

        if state_expect is not None:
            self.assertEqual(len(dwnldr.get_download_infos_by_state(state_expect)), len(urls))

    @classmethod
    def setUpClass(cls):
        # TODO _mock_responses() somehow doesn't work here, has to be investigated
        pass

    @classmethod
    def tearDownClass(cls):
        responses.reset()
        _delete_output(dir_out)

    @responses.activate
    def test_download_one(self):
        self._mock_responses()

        dwnldr = ImgDownloader(threads_max=threads_max)
        dwnldr.download(dir_out, False, url_jpeg_correct)
        dwnldr.wait_until_downloaded()

        self._check_if_downloaded(dwnldr, 1, ImgDownloadState.FINISHED, url_jpeg_correct)

    @responses.activate
    def test_download_one_then_another(self):
        self._mock_responses()

        dwnldr = ImgDownloader(threads_max=threads_max)

        # start downloading first task in the new thread, and after that next task, and so on.
        for url in urls_correct:
            dwnldr.download(dir_out, False, url)

        dwnldr.wait_until_downloaded()

        self._check_if_downloaded(dwnldr, len(urls_correct), ImgDownloadState.FINISHED, *urls_correct)

    @responses.activate
    def test_download_tasks_more_than_threads(self):
        self._mock_responses()

        # start downloading at the same N images. N should be more than maximum number of threads inside downloader.
        self.assertGreater(len(urls_correct), threads_max)
        dwnldr = ImgDownloader(threads_max=threads_max)
        dwnldr.download(dir_out, False, *urls_correct)
        dwnldr.wait_until_downloaded()

        # check the number of finished tasks
        self._check_if_downloaded(dwnldr, len(urls_correct), ImgDownloadState.FINISHED, *urls_correct)

    @responses.activate
    @patch('time.sleep', return_value=None)
    def test_download_url_wrong(self, patched_time_sleep):
        self._mock_responses()

        dwnldr = ImgDownloader(threads_max=threads_max)

        dwnldr.download(dir_out, False, url_wrong)
        dwnldr.wait_until_downloaded()

        # check the number ofr time.sleep calls
        self.assertEqual(dwnldr.DOWNLOAD_FAIL_MAX, patched_time_sleep.call_count)

        # check the number of finished tasks
        self.assertEqual(dwnldr.imgs_total, 1)
        # as download task was not successful it should have CANCELLED_ERROR state
        self.assertEqual(len(dwnldr.get_download_infos_by_state(ImgDownloadState.CANCELLED_ERROR)), 1)

        # check that image doesn't exist
        dwnld_info = dwnldr.get_download_info(url_wrong)
        self.assertFalse(os.path.exists(dwnld_info.path))

    @responses.activate
    def test_download_downloading(self):
        self._mock_responses()

        dwnldr = ImgDownloader(threads_max=threads_max)

        dwnldr.download(dir_out, False, url_jpeg_correct)
        # download again the same url - nothing should happen
        dwnldr.download(dir_out, False, url_jpeg_correct)
        dwnldr.wait_until_downloaded()
        # download again the same url - nothing should happen
        dwnldr.download(dir_out, False, url_jpeg_correct)

        self._check_if_downloaded(dwnldr, 1, ImgDownloadState.FINISHED, url_jpeg_correct)

    @responses.activate
    def test_download_img_name_exist(self):
        self._mock_responses()

        # create the file with the name of downloading image
        img_path = dir_out + img_jpeg_correct
        with open(img_path, 'w') as img_f:
            img_f.write("SOME RANDOM DATA")

        dwnldr = ImgDownloader(threads_max=threads_max)

        """ download the image which already exists. Set flag do_rewrite to True. Expected: image is downloaded
        and rewrites the existing one """

        dwnldr.download(dir_out, True, url_jpeg_correct)
        dwnldr.wait_until_downloaded()

        # check that image is really downloaded
        self._check_if_downloaded(dwnldr, 1, ImgDownloadState.FINISHED, url_jpeg_correct)

    @responses.activate
    @patch('time.sleep', return_value=None)
    def test_wait_until_downloaded(self, patched_time_sleep):
        self._mock_responses()

        dwnldr = ImgDownloader(threads_max=threads_max)

        n_callback_calls = 0  # local variable for number of
        def complete_callback(dwnld_info):
            nonlocal n_callback_calls
            n_callback_calls += 1

        urls_downloading = [url_wrong, url_jpeg_correct, url_png_correct]

        dwnldr.download(dir_out, False, *urls_downloading)
        dwnldr.cancel(url_jpeg_correct)
        dwnldr.wait_until_downloaded(complete_callback)
        # make sure that callback function was called N times, where N is equal to the number of downloading images
        self.assertEqual(n_callback_calls, len(urls_downloading))
        dwnldr.wait_until_downloaded(complete_callback)
        """ make sure that callback function is not called, because all information about download task was already
        sent with the previous call of wait_until_downloaded """
        self.assertEqual(n_callback_calls, len(urls_downloading))

    @responses.activate
    def test_cancel_one(self):
        self._mock_responses()

        dwnldr = ImgDownloader(threads_max=threads_max)
        dwnldr.download(dir_out, False, url_jpeg_correct)
        dwnldr.cancel(url_jpeg_correct)

        # check the number of finished tasks
        self.assertEqual(dwnldr.imgs_total, 1)
        self.assertEqual(len(dwnldr.get_download_infos_by_state(ImgDownloadState.CANCELLED)), 1)

    @responses.activate
    def test_canel_all(self):
        self._mock_responses()

        # start downloading at the same N images. N should be more than maximum number of threads inside downloader.
        dwnldr = ImgDownloader(threads_max=threads_max)
        dwnldr.download(dir_out, False, *urls_correct)
        dwnldr.cancel(*urls_correct)

        # check the number of finished tasks
        self.assertEqual(dwnldr.imgs_total, len(urls_correct))
        self.assertEqual(len(dwnldr.get_download_infos_by_state(ImgDownloadState.CANCELLED)), len(urls_correct))

    @responses.activate
    def test_cancel_url_not_exist(self):
        self._mock_responses()

        dwnldr = ImgDownloader(threads_max=threads_max)
        dwnldr.download(dir_out, False, url_wrong)
        dwnldr.cancel(url_wrong)

        # check the number of finished tasks
        self.assertEqual(dwnldr.imgs_total, 1)
        self.assertEqual(len(dwnldr.get_download_infos_by_state(ImgDownloadState.CANCELLED)), 1)

    @responses.activate
    def test_cancel_canceled(self):
        self._mock_responses()

        dwnldr = ImgDownloader(threads_max=threads_max)
        dwnldr.download(dir_out, False, url_jpeg_correct)
        dwnldr.cancel(url_jpeg_correct)

        # check the number of finished tasks
        self.assertEqual(dwnldr.imgs_total, 1)
        self.assertEqual(len(dwnldr.get_download_infos_by_state(ImgDownloadState.CANCELLED)), 1)

        # cancel already cancelled task. Expected: nothing should happen
        dwnldr.cancel(url_jpeg_correct)
        self.assertEqual(dwnldr.imgs_total, 1)
        self.assertEqual(len(dwnldr.get_download_infos_by_state(ImgDownloadState.CANCELLED)), 1)

    @responses.activate
    def test_remove_one(self):
        self._mock_responses()

        dwnldr = ImgDownloader(threads_max=threads_max)
        dwnldr.download(dir_out, False, url_jpeg_correct)
        # remove directly after download is started
        dwnldr.remove(url_jpeg_correct)

        # check the number of finished tasks
        self.assertEqual(dwnldr.imgs_total, 0)
        self.assertEqual(len(dwnldr.get_download_infos_by_state(ImgDownloadState.CANCELLED)), 0)
        self.assertEqual(len(dwnldr.get_download_infos_by_state(ImgDownloadState.FINISHED)), 0)
        self.assertEqual(len(dwnldr.get_download_infos_by_state(ImgDownloadState.PENDING)), 0)
        self.assertEqual(len(dwnldr.get_download_infos_by_state(ImgDownloadState.RUNNING)), 0)

    @responses.activate
    def test_remove_all(self):
        self._mock_responses()

        dwnldr = ImgDownloader(threads_max=threads_max)
        dwnldr.download(dir_out, False, *urls_correct)
        # wait until downloading is finished
        dwnldr.wait_until_downloaded()

        # remove all download tasks
        dwnldr.remove(*urls_correct)
        self.assertEqual(dwnldr.imgs_total, 0)
        self.assertEqual(len(dwnldr.get_download_infos_by_state(ImgDownloadState.FINISHED)), 0)

    @responses.activate
    def test_restart_all(self):
        self._mock_responses()

        dwnldr = ImgDownloader(threads_max=threads_max)
        dwnldr.download(dir_out, False, *urls_correct)
        # restart during tasks are running
        dwnldr.restart(*urls_correct)
        dwnldr.wait_until_downloaded()

        self._check_if_downloaded(dwnldr, len(urls_correct), ImgDownloadState.FINISHED, *urls_correct)

        # restart tasks again
        dwnldr.restart(*urls_correct)
        dwnldr.wait_until_downloaded()

        self._check_if_downloaded(dwnldr, len(urls_correct), ImgDownloadState.FINISHED, *urls_correct)

    @responses.activate
    @patch('time.sleep', return_value=None)
    def test_restart_url_not_exist(self, patched_time_sleep):
        self._mock_responses()

        dwnldr = ImgDownloader(threads_max=threads_max)
        dwnldr.download(dir_out, False, url_wrong)
        # restart immidiately after download is started
        patched_time_sleep.call_count = 0
        dwnldr.restart(url_wrong)
        dwnldr.wait_until_downloaded()

        # check the number of finished tasks
        self.assertEqual(dwnldr.imgs_total, 1)
        self.assertEqual(len(dwnldr.get_download_infos_by_state(ImgDownloadState.CANCELLED_ERROR)), 1)

        # restart again task with the wrong url
        dwnldr.restart(url_wrong)
        dwnldr.wait_until_downloaded()

        self.assertEqual(dwnldr.DOWNLOAD_FAIL_MAX * 2, patched_time_sleep.call_count)

        self.assertEqual(dwnldr.imgs_total, 1)
        self.assertEqual(len(dwnldr.get_download_infos_by_state(ImgDownloadState.CANCELLED_ERROR)), 1)

    @responses.activate
    def test_restart_img_exist(self):
        self._mock_responses()

        # create the file with the name of downloading image
        img_path = dir_out + img_jpeg_correct
        with open(img_path, 'w') as img_f:
            img_f.write("SOME RANDOM DATA")

        dwnldr = ImgDownloader(threads_max=threads_max)

        """ download the image which already exists. Set flag do_rewrite to False. Expected: image is downloaded
        and saved under the second name """

        dwnldr.download(dir_out, False, url_jpeg_correct)
        dwnldr.wait_until_downloaded()

        # check that image is really downloaded
        dwnld_info = dwnldr.get_download_info(url_jpeg_correct)
        self.assertTrue(os.path.exists(dwnld_info.path))
        self.assertNotEqual(dwnld_info.path, img_path)

        # restart the download. Expected: the image with the second name is rewritten
        dwnldr.restart(url_jpeg_correct)
        dwnldr.wait_until_downloaded()
        dwnld_info_restarted = dwnldr.get_download_info(url_jpeg_correct)
        self.assertEqual(dwnld_info.path, dwnld_info_restarted.path)
        pass

    @responses.activate
    @patch('time.sleep', return_value=None)
    def test_get_methods(self, patched_time_sleep):
        self._mock_responses()

        dwnldr = ImgDownloader(threads_max=threads_max)
        urls_downloading = [url_wrong, url_jpeg_correct, url_png_correct]

        dwnldr.download(dir_out, False, *urls_downloading)
        dwnldr.cancel(url_jpeg_correct)
        dwnldr.wait_until_downloaded()

        urls_downloaded = dwnldr.get_urls()
        # the same amount and same order is expected
        self.assertEqual(len(urls_downloading), len(urls_downloaded))

        # check the number of FINISHED/CANCELLED/CANCELLED_ERROR tasks)
        self.assertEqual(len(dwnldr.get_download_infos_by_state(ImgDownloadState.FINISHED)), 1)
        self.assertEqual(len(dwnldr.get_download_infos_by_state(ImgDownloadState.CANCELLED)), 1)
        self.assertEqual(len(dwnldr.get_download_infos_by_state(ImgDownloadState.CANCELLED_ERROR)), 1)

if __name__ == '__main__':
    unittest.main()