import threading
from heapq import nsmallest
from tweepy import Stream
from tweepy import OAuthHandler
from tweepy.streaming import StreamListener
import logging
import matplotlib.pyplot as plt
import sys
import config
import _tkinter


class TopTrendsModel:
    """ This class is made for single writer (many writes), single reader (few reads) """

    def __init__(self, max_num_of_trends):
        self._lock = threading.Lock()
        self._min_trending_count = 0
        self._trending = {}
        self._max_num_of_trends = max_num_of_trends

    def insert_trend(self, trend_count, trend_name):
        if self._check_insert_conditions_no_lock(trend_count):
            with self._lock:
                self._trending[trend_name] = trend_count
                self._handle_arr_min_and_capacity()

    def _check_insert_conditions_no_lock(self, trend_count):
        return (trend_count > self._min_trending_count) or (len(self._trending) < self._max_num_of_trends)

    def _handle_arr_min_and_capacity(self):
        if len(self._trending) > self._max_num_of_trends:
            two_smallest_trends = nsmallest(2, self._trending, key=self._trending.get)
            del self._trending[two_smallest_trends[0]]
            self._min_trending_count = self._trending[two_smallest_trends[1]]
        else:
            min_trending_name = min(self._trending, key=self._trending.get)
            self._min_trending_count = self._trending[min_trending_name]

    def get_trends(self):
        with self._lock:
            return self._trending.copy()  # The copy price is low because of the few reads


class Trie:
    """ This is a basic implementation of the Trie data-structure. """

    def __init__(self, key=None):
        self.key = key
        self.key_counter = 0
        self._children = []

    def insert(self, word):
        if len(word) == 0:  # stop condition
            self.key_counter += 1
            return self.key_counter

        transition_letter = word[0]
        sub_string = word[1:]

        for child in self._children:
            if child.key == transition_letter:
                return child.insert(sub_string)

        new_letter_child = Trie(transition_letter)
        self._children.append(new_letter_child)
        return new_letter_child.insert(sub_string)


class TwitterTrendConsumer(StreamListener):
    """ This object handles the incoming tweets and update the model with incoming trends. """

    def __init__(self, top_trends_model, api=None):
        super().__init__(api)
        self._top_trends_model = top_trends_model
        # The Tire data structure save as a compressed cache - this helps to keep the memory consumption to a minimum.
        self._hashtag_memory = Trie()

    def on_connect(self):
        logging.debug("Connected to twitter streaming API")

    def on_status(self, status):
        for hashtag_obj in status.entities["hashtags"]:
            hashtag_text = hashtag_obj["text"].lower()  # In trend counting, I disregard case differences

            curr_hashtag_count = self._hashtag_memory.insert(hashtag_text)
            self._top_trends_model.insert_trend(curr_hashtag_count, hashtag_text)

    def on_error(self, status):
        if status == 401:
            logging.error("Invalid credentials. connection refused by twitter API. Status : 401.")
        else:
            logging.error(status)

    def on_timeout(self):
        logging.error("The connection to the streaming API has timed-out.")


class TopTrendsView:
    """ This object handles the UI side of the bar-chart.  """

    def __init__(self, top_trends_model):
        self._fig = None
        self._ax = None
        self._top_trends_model = top_trends_model
        self.is_running = False
        self._current_hist_obj = None
        plt.ion()

    def __enter__(self):
        self._fig = plt.figure(1, [13, 5])
        self._ax = self._fig.add_subplot(111)
        self._current_hist_obj = None
        self.is_running = True
        self._fig.canvas.mpl_connect('close_event', self.__exit__)
        return self

    def update_hist(self):
        hist_obj = self._top_trends_model.get_trends()
        logging.debug("Current trends model: {}".format(str(hist_obj)))
        if (hist_obj is not None) and (len(hist_obj) > 0):
            # Redraw histogram only if it's different from the one currently shown to the user
            if self._current_hist_obj == hist_obj:
                return
            self._ax.clear()
            self._ax.barh(list(hist_obj.keys()), hist_obj.values(), 0.75, color='g')
            for i, v in enumerate(hist_obj.values()):
                self._ax.text(v + 0.005, i, str(v), color='g')

    def __exit__(self, exc_type=None, exc_value=None, traceback=None):
        if self.is_running:
            self.is_running = False
            logging.info("Closing the TopTrendsView")


def create_twitter_consumer(credential, top_trends_model):
    """ Init all authentication data required for the Twitter API and create the stream object """

    auth = OAuthHandler(credential.ckey, credential.csecret)
    auth.set_access_token(credential.atoken, credential.asecret)

    return Stream(auth, TwitterTrendConsumer(top_trends_model), daemon=True)


def main():
    logging.basicConfig(
        format=config.Logger.log_msg_format, level=config.Logger.log_level, datefmt=config.Logger.Log_date_format)

    if len(sys.argv) < 2:
        # No filtering keywords has been given by the user
        print("The twitterTrendsDisplayer must have at least one filtering keyword as an argument. Try again. ")
        return
    else:
        twitter_filter_keywords = sys.argv[1:]
    logging.info(
        "The following keywords will be used to filter the incoming twitter feed: {}. Max num of trends to display: {}"
            .format(str(twitter_filter_keywords).strip('[]'), str(config.Application.num_of_trends)))

    top_trends_model = TopTrendsModel(config.Application.num_of_trends)

    twitter_stream = create_twitter_consumer(config.TwitterAPICredential, top_trends_model)
    twitter_stream.filter(track=twitter_filter_keywords, is_async=True)

    with TopTrendsView(top_trends_model) as top_trends_view:
        while top_trends_view.is_running:
            try:
                top_trends_view.update_hist()
                plt.pause(config.Application.time_between_UI_updates_seconds)
                plt.draw()
            except _tkinter.TclError:
                # This except case is triggered when the event of "UI window closing" is raised.
                break
            except Exception as exp:
                logging.error(exp)
                break
    twitter_stream.disconnect()


if __name__ == "__main__":
    main()
