功能：
=====
用于访问和下载某人的全部推特,以及大范围的推特爬取
介绍：
=====
有研究过推特的API，一般只能抓取到7天以为的推特，而且同一个开发者账号爬虫等会有时间内会有限制
这是我通过改写一个开源项目抓取某个人以来的所有推特，原理是通过不停的模拟浏览器滑动获取json文件，当然
过程中并没有用到类似于selenium一类的中间件
安装：
=====
在pycharm开发环境或者linux系统cmd下输入以下指令：
pip install GetOldTweets3

输出：
=====
默认输出为output_got.csv的文件


使用方法举例(linux)：
=====

Example 1 获取搜索的推特内容（--maxtweets 表示获取的最大数量）

### 		GetOldTweets3 --querysearch "europe refugees" --maxtweets 10

Example 2 - 通过user_id获取推特,如获取川普的前10条推特

### 		GetOldTweets3 --username "realDonaldTrump" --toptweets --maxtweets 30

Example 3 - 通过user_id时间段内的推特

### 		GetOldTweets3 --username "barackobama" --since 2015-09-10 --until 2015-09-12 --maxtweets 10

Example 4 - 获取某种语言的推特:

### 		GetOldTweets3 --querysearch "bitcoin" --lang cn --maxtweets 10


Example 5 - 通过地理位置获取推特:

### 		GetOldTweets3 --querysearch "bitcoin" --near "Berlin, Germany" --within 25km --maxtweets 10


如何在windows下使用
=====
直接下载项目后在前面加python即可
如：
### 	python GetOldTweets3 --username "barackobama" --toptweets --maxtweets 10

#后续的功能，如一键获取用户的关注人，地理信息，签名，所发推特的评论等功能正在添加中（需要用到开发者账号）
