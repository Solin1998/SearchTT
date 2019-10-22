# -*- coding: utf-8 -*-

import json, re, datetime, sys, random, http.cookiejar
import urllib.request, urllib.parse, urllib.error
from pyquery import PyQuery
from .. import models

class TweetManager:
    """A class for accessing the Twitter's search engine"""
    def __init__(self):
        pass

    user_agents = [
        'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:63.0) Gecko/20100101 Firefox/63.0',
        'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:62.0) Gecko/20100101 Firefox/62.0',
        'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:61.0) Gecko/20100101 Firefox/61.0',
        'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:63.0) Gecko/20100101 Firefox/63.0',
        'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.77 Safari/537.36',
        'Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.77 Safari/537.36',
        'Mozilla/5.0 (Windows NT 6.1; Trident/7.0; rv:11.0) like Gecko',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.0 Safari/605.1.15',
    ]

    @staticmethod
    def getTweets(tweetCriteria, receiveBuffer=None, bufferLength=100, proxy=None, debug=False):
        """Get tweets that match the tweetCriteria parameter
        A static method.

        Parameters
        ----------
        tweetCriteria : tweetCriteria, an object that specifies a match criteria
        receiveBuffer : callable, a function that will be called upon a getting next `bufferLength' tweets
        bufferLength: int, the number of tweets to pass to `receiveBuffer' function
        proxy: str, a proxy server to use
        debug: bool, output debug information
        """
        results = []
        resultsAux = []
        cookieJar = http.cookiejar.CookieJar()
        user_agent = random.choice(TweetManager.user_agents)

        all_usernames = []
        usernames_per_batch = 20

        if hasattr(tweetCriteria, 'username'):
            if type(tweetCriteria.username) == str or not hasattr(tweetCriteria.username, '__iter__'):
                tweetCriteria.username = [tweetCriteria.username]

            usernames_ = [u.lstrip('@') for u in tweetCriteria.username if u]
            all_usernames = sorted({u.lower() for u in usernames_ if u})
            n_usernames = len(all_usernames)
            n_batches = n_usernames // usernames_per_batch + (n_usernames % usernames_per_batch > 0)
        else:
            n_batches = 1

        for batch in range(n_batches):  # process all_usernames by batches
            refreshCursor = ''
            batch_cnt_results = 0

            if all_usernames:  # a username in the criteria?
                tweetCriteria.username = all_usernames[batch*usernames_per_batch:batch*usernames_per_batch+usernames_per_batch]

            active = True
            while active:
                json = TweetManager.getJsonResponse(tweetCriteria, refreshCursor, cookieJar, proxy, user_agent, debug=debug)
                if len(json['items_html'].strip()) == 0:
                    break

                refreshCursor = json['min_position']
                scrapedTweets = PyQuery(json['items_html'])
                #Remove incomplete tweets withheld by Twitter Guidelines
                scrapedTweets.remove('div.withheld-tweet')
                tweets = scrapedTweets('div.js-stream-tweet')

                if len(tweets) == 0:
                    break

                for tweetHTML in tweets:
                    tweetPQ = PyQuery(tweetHTML)
                    tweet = models.Tweet()

                    usernames = tweetPQ("span.username.u-dir b").text().split()
                    if not len(usernames):  # fix for issue #13
                        continue

                    tweet.username = usernames[0]
                    tweet.to = usernames[1] if len(usernames) >= 2 else None  # take the first recipient if many
                    rawtext = TweetManager.textify(tweetPQ("p.js-tweet-text").html(), tweetCriteria.emoji)
                    tweet.text = re.sub(r"\s+", " ", rawtext)\
                        .replace('# ', '#').replace('@ ', '@').replace('$ ', '$')
                    tweet.retweets = int(tweetPQ("span.ProfileTweet-action--retweet span.ProfileTweet-actionCount").attr("data-tweet-stat-count").replace(",", ""))
                    tweet.favorites = int(tweetPQ("span.ProfileTweet-action--favorite span.ProfileTweet-actionCount").attr("data-tweet-stat-count").replace(",", ""))
                    tweet.replies = int(tweetPQ("span.ProfileTweet-action--reply span.ProfileTweet-actionCount").attr("data-tweet-stat-count").replace(",", ""))
                    tweet.id = tweetPQ.attr("data-tweet-id")
                    tweet.permalink = 'https://twitter.com' + tweetPQ.attr("data-permalink-path")
                    tweet.author_id = int(tweetPQ("a.js-user-profile-link").attr("data-user-id"))

                    dateSec = int(tweetPQ("small.time span.js-short-timestamp").attr("data-time"))
                    tweet.date = datetime.datetime.fromtimestamp(dateSec, tz=datetime.timezone.utc)
                    tweet.formatted_date = datetime.datetime.fromtimestamp(dateSec, tz=datetime.timezone.utc)\
                                                            .strftime("%a %b %d %X +0000 %Y")
                    tweet.mentions = " ".join(re.compile('(@\\w*)').findall(tweet.text))
                    tweet.hashtags = " ".join(re.compile('(#\\w*)').findall(tweet.text))

                    geoSpan = tweetPQ('span.Tweet-geo')
                    if len(geoSpan) > 0:
                        tweet.geo = geoSpan.attr('title')
                    else:
                        tweet.geo = ''

                    urls = []
                    for link in tweetPQ("a"):
                        try:
                            urls.append((link.attrib["data-expanded-url"]))
                        except KeyError:
                            pass

                    tweet.urls = ",".join(urls)

                    results.append(tweet)
                    resultsAux.append(tweet)
                    
                    if receiveBuffer and len(resultsAux) >= bufferLength:
                        receiveBuffer(resultsAux)
                        resultsAux = []

                    batch_cnt_results += 1
                    if tweetCriteria.maxTweets > 0 and batch_cnt_results >= tweetCriteria.maxTweets:
                        active = False
                        break

            if receiveBuffer and len(resultsAux) > 0:
                receiveBuffer(resultsAux)
                resultsAux = []

        return results

    @staticmethod
    def textify(html, emoji):
        """Given a chunk of text with embedded Twitter HTML markup, replace
        emoji images with appropriate emoji markup, replace links with the original
        URIs, and discard all other markup.
        """
        # Step 0, compile some convenient regular expressions
        imgre = re.compile("^(.*?)(<img.*?/>)(.*)$")
        charre = re.compile("^&#x([^;]+);(.*)$")
        htmlre = re.compile("^(.*?)(<.*?>)(.*)$")
        are = re.compile("^(.*?)(<a href=[^>]+>(.*?)</a>)(.*)$")

        # Step 1, prepare a single-line string for re convenience
        puc = chr(0xE001)
        html = html.replace("\n", puc)

        # Step 2, find images that represent emoji, replace them with the
        # Unicode codepoint of the emoji.
        text = ""
        match = imgre.match(html)
        while match:
            text += match.group(1)
            img = match.group(2)
            html = match.group(3)

            attr = TweetManager.parse_attributes(img)
            if emoji == "unicode":
                chars = attr["alt"]
                match = charre.match(chars)
                while match:
                    text += chr(int(match.group(1),16))
                    chars = match.group(2)
                    match = charre.match(chars)
            elif emoji == "named":
                text += "Emoji[" + attr['title'] + "]"
            else:
                text += " "

            match = imgre.match(html)
        text = text + html

        # Step 3, find links and replace them with the actual URL
        html = text
        text = ""
        match = are.match(html)
        while match:
            text += match.group(1)
            link = match.group(2)
            linktext = match.group(3)
            html = match.group(4)

            attr = TweetManager.parse_attributes(link)
            if "u-hidden" in attr["class"]:
                pass
            elif "data-expanded-url" in attr \
               and "twitter-timeline-link" in attr["class"]:
                text += attr['data-expanded-url']
            else:
                text += link

            match = are.match(html)
        text = text + html

        # Step 4, discard any other markup that happens to be in the tweet.
        # This makes textify() behave like tweetPQ.text()
        html = text
        text = ""
        match = htmlre.match(html)
        while match:
            text += match.group(1)
            html = match.group(3)
            match = htmlre.match(html)
        text = text + html

        # Step 5, make the string multi-line again.
        text = text.replace(puc, "\n")
        return text

    @staticmethod
    def parse_attributes(markup):
        """Given markup that begins with a start tag, parse out the tag name
        and the attributes. Return them in a dictionary.
        """
        gire = re.compile("^<([^\s]+?)(.*?)>.*")
        attre = re.compile("^.*?([^\s]+?)=\"(.*?)\"(.*)$")
        attr = {}

        match = gire.match(markup)
        if match:
            attr['*tag'] = match.group(1)
            markup = match.group(2)

            match = attre.match(markup)
            while match:
                attr[match.group(1)] = match.group(2)
                markup = match.group(3)
                match = attre.match(markup)

        return attr

    @staticmethod
    def getJsonResponse(tweetCriteria, refreshCursor, cookieJar, proxy, useragent=None, debug=False):
        """Invoke an HTTP query to Twitter.
        Should not be used as an API function. A static method.
        """
        url = "https://twitter.com/i/search/timeline?"

        if not tweetCriteria.topTweets:
            url += "f=tweets&"

        url += ("vertical=news&q=%s&src=typd&%s"
                "&include_available_features=1&include_entities=1&max_position=%s"
                "&reset_error_state=false")

        urlGetData = ''

        if hasattr(tweetCriteria, 'querySearch'):
            urlGetData += tweetCriteria.querySearch

        if hasattr(tweetCriteria, 'username'):
            if not hasattr(tweetCriteria.username, '__iter__'):
                tweetCriteria.username = [tweetCriteria.username]

            usernames_ = [u.lstrip('@') for u in tweetCriteria.username if u]
            tweetCriteria.username = {u.lower() for u in usernames_ if u}

            usernames = [' from:'+u for u in sorted(tweetCriteria.username)]
            if usernames:
                urlGetData += ' OR'.join(usernames)

        if hasattr(tweetCriteria, 'within'):
            if hasattr(tweetCriteria, 'near'):
                urlGetData += ' near:"%s" within:%s' % (tweetCriteria.near, tweetCriteria.within)
            elif hasattr(tweetCriteria, 'lat') and hasattr(tweetCriteria, 'lon'):
                urlGetData += ' geocode:%f,%f,%s' % (tweetCriteria.lat, tweetCriteria.lon, tweetCriteria.within)

        if hasattr(tweetCriteria, 'since'):
            urlGetData += ' since:' + tweetCriteria.since

        if hasattr(tweetCriteria, 'until'):
            urlGetData += ' until:' + tweetCriteria.until

        if hasattr(tweetCriteria, 'lang'):
            urlLang = 'l=' + tweetCriteria.lang + '&'
        else:
            urlLang = ''
        url = url % (urllib.parse.quote(urlGetData.strip()), urlLang, urllib.parse.quote(refreshCursor))
        useragent = useragent or TweetManager.user_agents[0]

        headers = [
            ('Host', "twitter.com"),
            ('User-Agent', useragent),
            ('Accept', "application/json, text/javascript, */*; q=0.01"),
            ('Accept-Language', "en-US,en;q=0.5"),
            ('X-Requested-With', "XMLHttpRequest"),
            ('Referer', url),
            ('Connection', "keep-alive")
        ]

        if proxy:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({'http': proxy, 'https': proxy}), urllib.request.HTTPCookieProcessor(cookieJar))
        else:
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookieJar))
        opener.addheaders = headers

        if debug:
            print(url)
            print('\n'.join(h[0]+': '+h[1] for h in headers))

        try:
            response = opener.open(url)
            jsonResponse = response.read()
        except Exception as e:
            print("An error occured during an HTTP request:", str(e))
            print("Try to open in browser: https://twitter.com/search?q=%s&src=typd" % urllib.parse.quote(urlGetData))
            sys.exit()

        try:
            s_json = jsonResponse.decode()
        except:
            print("Invalid response from Twitter")
            sys.exit()

        try:
            dataJson = json.loads(s_json)
        except:
            print("Error parsing JSON: %s" % s_json)
            sys.exit()

        if debug:
            print(s_json)
            print("---\n")

        return dataJson
