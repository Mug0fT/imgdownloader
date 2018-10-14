import unittest
import os
import shutil
import time

from imgdownloader.urlsextractor import *

file_path_urls = 'tests/support/urls.txt'
urls_in_file = ["https://habrastorage.org/webt/y0/nc/6i//y0nc6ianhueuc3tqnwkn5qbl0h4.jpeg",
                "https://habrastorage.org/webt/54/1e/jo/541ejotttsu8hl3swtihly-liro.png",
                "https://habrastorage.org/getpro/habr/post_images/fbd/8c6/915/fbd8c69158dc31ae76206418b3e48198.jpg"]


lines_in_file = [urls_in_file[0] + '\n',
                '    ' + urls_in_file[1] + '    ' + '\r\n',
                '\r' + urls_in_file[2] + '\n\n']

n_invalid_lines = 3  # pleas make sure that this number is always synchronized with lines_in_file @TDOO can be better done

def delete_file(file_path):
    # try to remove the fileif exists
    if os.path.exists(file_path):
        # print("Deleting output directory")

        t = 0
        # wait max 5 seconds until directory is deleted
        while os.path.exists(file_path) and t < 5:  # check if it exists
            try:
                os.remove(file_path)
            except:
                t += 0.5
                time.sleep(0.5)


class UrlsExtractorTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(file_path_urls, 'w') as f:
            for line in lines_in_file:
                f.write(line)

    @classmethod
    def tearDownClass(cls):
        delete_file(file_path_urls)


    def test_get_urls(self):
        err_cnt = 0
        def log(text):
            nonlocal err_cnt
            err_cnt += 1

        urls_extracted = get_urls(file_path_urls, logger_func = log)
        self.assertEqual(len(urls_extracted), len(urls_in_file))

        # make sure that expected urls were extracted (order is not important)
        for url in urls_extracted:
            self.assertTrue(url in urls_in_file)

        # we expect that some lines have invalid urls
        self.assertEqual(err_cnt, n_invalid_lines)
        # make sure that spaces and new line symbols are removed

    def test_get_urls_file_cantbe_open(self):
        with self.assertRaises(FileNotFoundError):
            get_urls(file_path_urls + 'WRONG')