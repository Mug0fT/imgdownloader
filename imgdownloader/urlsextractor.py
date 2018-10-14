from urllib.parse import urlparse


def get_urls(file_path, logger_func=None):
    """
    Reads the specified file and returns found URLs. Each line in the file has to contain only one URL.
    All spaces are ignored. In case of empty on invalid line logger_func will be called with the information
    about invalid line number.
    In case file_path is invalid or file can't be open, exception will be raised. Please see @os.open for
    description of possible exceptions.

    :param file_path: path to the file with URLs
    :param logger_func: callback function which will be called in case URLs is not found in the line. The string
    with error information and line number is passed to this function.
    :type logger_func: callbackFunction(error_text)
    :return: list of extracted URLs
    """
    urls = []

    def log(error_text):
        if logger_func is not None:
            logger_func(error_text)
        return True

    with open(file_path) as f:
        line_n = 0
        for url in f:
            # remove all spaces and new lines
            url = url.strip()

            # check if URL is valid
            url_parsed = urlparse(url)
            is_url_valid = bool(url_parsed.scheme)
            if not is_url_valid:
                log("Line %u contains invalid URL" % line_n)

            # @TODO filtering by image extensions can be easily implemented if necessary
            if is_url_valid:
                urls.append(url)

            line_n += 1

    return urls