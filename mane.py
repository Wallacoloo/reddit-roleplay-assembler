#!/usr/bin/python

# Requirements: 
#   install unidecode, html2text, jinja2, PRAW (Python Reddit API Wrapper) and requests
#     e.g. `pip install unidecode html2text jinja2 praw requests`

# This script reads through a reddit thread, finds the deepest comment, and walks down the chain to it,
# Compiling all comments in that chain into a single page.
# This is good for things like role-playing where everything is supposed to happen chronologically 
#   and the number of comments grows absurdly.


import base64, itertools, json, os.path, sys, time
from collections import defaultdict

# Import dependencies that don't always ship with python
prereqs = "unidecode", "html2text", "jinja2", "praw", "requests"
missing_deps = []
for p in prereqs:
	try:
		globals()[p] = __import__(p)
	except ImportError:
		missing_deps.append(p)

if missing_deps:
	raise ImportError("Prerequisite(s) not met: [%s]" %(", ").join(missing_deps))


def reverse_enumerate(iterable):
	"""
	Enumerate over an iterable in reverse order while retaining proper indexes
	"""
	# Lifted from http://galvanist.com/post/53478841501/python-reverse-enumerate
	return itertools.izip(reversed(xrange(len(iterable))), reversed(iterable))

class ThreadProcessor(object):
	@property
	def thread(self):
		"""
		Only load the thread if/when it's actually needed.
		"""
		if self._thread is None:
			self._thread = self.reddit.get_submission(submission_id=self.thread_id)
		return self._thread

	@property
	def subreddit(self):
		return self.thread.subreddit
	
	
	def __init__(self, thread_id=None, json=None, author_map=None, characters=None):
		"""
		Create an object to do various processing with a reddit thread (rendering to different formats).
		thread_id is the optional id of the reddit submission to squash (check the URL).
			If thread_id is not None, the thread will be remotely fetched and parsed from reddit 
			(this can easily take an hour if the number of comments exceeds a few thousand).
		json is an optional cached/pre-parsed version of the thread. 
			Equivalent to initializing with a thread_id, and saving self.json to a file
		"""
		self._thread = None
		self.thread_id = thread_id
		self.comment_data = None
		self.author_map = author_map or {}
		self.characters = characters or {}
		# Create a handle for accessing reddit, and load the thread
		self.reddit = praw.Reddit(user_agent='github.com/wallacoloo/reddit-roleplay-assembler')

		if json is not None:
			self.comment_data = globals()["json"].loads(json)
		if self.comment_data is None and thread_id is not None:
			# Many functions recurse through the comment chain, so set a high recursion limit
			sys.setrecursionlimit(5*self.thread.num_comments+1000)

			# Expand all comments (this will take some time!)
			self.thread.replace_more_comments(limit=None, threshold=1)

			# Remove all but the main thread of comments
			max_depth = self.max_comment_depth()
			self.filter_comments_by_max_depth(max_depth)

			# There may still be comment forks near the end that have the same length
			# We need to drop everything after the fork, as we don't know which of the choices is the main discussion
			flattened = self.flatten()
			self.comment_data = self.comments_to_dicts(flattened)

	def max_comment_depth(self, comment=None, cur_depth=0):
		"""
		Given a comment (defaults to thread root), find the maximum depth of its descendents
		"""
		if comment is None:
			comment = self.thread
		replies = comment.replies if isinstance(comment, praw.objects.Comment) else \
			(comment.comments if isinstance(comment, praw.objects.Submission) else None)
		if replies:
			return max(self.max_comment_depth(reply, cur_depth=cur_depth+1) for reply in replies)
		else:
			return cur_depth

	def filter_comments_by_max_depth(self, max_depth, comments=None):
		"""
		Delete all comments which don't have any descendents at depths >= max_depth
		"""
		if comments is None: 
			comments = self.thread.comments
		for i, c in reverse_enumerate(comments):
			# If the comment has no children at a sufficient depth, delete it altogether,
			# Else apply the same algorithm to its children
			if self.max_comment_depth(c) < max_depth-1:
				del comments[i]
			elif isinstance(c, praw.objects.Comment):
				self.filter_comments_by_max_depth(max_depth=max_depth-1, comments=c.replies)

	def flatten(self):
		"""
		Flattens a chain of comments,
		but stops if it gets to an ambiguous point where a comment has more than one child (or no children)
		"""
		comment = self.thread.comments[0]
		while isinstance(comment, praw.objects.Comment) and len(comment.replies) == 1:
			yield comment
			comment = comment.replies[0]

	def comments_to_dicts(self, comments):
		"""
		Serialize a flat sequence of comments into an array of dicts that can easily be serialized to JSON.
		"""
		list_of_dicts = [{ "author": c.author.name, "body_html":c.body_html, 
		"created_utc":c.created_utc, "permalink":c.permalink } for c in comments]
		return list_of_dicts
	def get_json(self):
		"""
		Return the flat comment array formatted as a JSON string to easily store in a file, etc.
		"""
		return json.dumps(self.comment_data)
	def get_html(self):
		"""
		Render a webpage out of the flattened comment data (Experimental)
		"""
		env = jinja2.Environment(loader=jinja2.PackageLoader('mane', 'templates'))
		template = env.get_template('basic.html')

		# Embed subreddit's css into the html page:
		style_info = self.subreddit.get_stylesheet()
		subreddit_css = style_info["stylesheet"]
		images = style_info["images"]
		# substitute image urls
		for im in images:
			im_req = requests.get(im["url"])
			mime_type = im_req.headers["content-type"]
			as_b64 = base64.b64encode(im_req.content)
			subreddit_css = subreddit_css.replace(im["link"], "url(data:%s;base64,%s)" % (mime_type, as_b64))

		# in case not all authors were accounted for, map unknown authors to character "unknown"
		author_names = set(c["author"] for c in self.comment_data)
		default_author_map = dict((author, u"unknown") for author in author_names)
		author_map = default_author_map
		author_map.update(self.author_map)

		return template.render(unidecode=unidecode, time=time, 
			subreddit_css=subreddit_css, 
			author_map=author_map, characters=self.characters,
			comments=self.comment_data, title="")
	def get_txt(self):
		"""
		Flatten the thread to a plain-text view, in which each comment is separated by an empty line.
		Comments are encoded as "<author-name>:text" (brackets are included)
		"""
		encoder = html2text.HTML2Text()
		# Default <a href="path">text</a> encodes to "[text](path)""
		# Configure it to encode to just "text" instead
		encoder.ignore_links = True
		as_unicode = "\n\n".join("<%s>: %s" %(self.author_map.get(c["author"], c["author"]), 
									encoder.handle(c["body_html"]).strip())
			for c in self.comment_data)
		return unidecode.unidecode(as_unicode)

def mane():
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument("-t", "--thread", type=str,
        help="id of the reddit thread to process")
	parser.add_argument("--json", action="store_true",
		help="store the flattened thread in json format")
	parser.add_argument("--txt", action="store_true",
		help="render a human-readable .txt file from the flattened thread")
	parser.add_argument("--html", action="store_true",
		help="render html webpage from the flattened thread")
	parser.add_argument("-a", "--author", type=str, action="append",
		help="""map a reddit username to a character.
e.g. -a Wallacoloo,Gandalf means that Wallacoloo plays as Gandalf throughout the story""")
	parser.add_argument("--character-color", type=str, action="append",
		help="""associate a color value with a character (used for text/background color).
e.g. --character-color Gandalf,#333355 makes Gandalf a dark blue""")
	args = parser.parse_args()

	if args.thread:
		json = None
		thread_id = args.thread
		if os.path.isfile("%s.json" % args.thread):
			# We can use the cached json output
			json = open("%s.json" % args.thread, "r").read()

		author_map = dict(a.split(",") for a in args.author)
		# Build a dictionary that maps character names to dicts containing {"color": html_color}
		characters = defaultdict(dict)
		for char_color in args.character_color:
			char, color = char_color.split(",")
			characters[char]["color"] = color

		processor = ThreadProcessor(thread_id=thread_id, json=json, author_map=author_map, characters=characters)

		if args.json:
			# store json output to `thread_id`.json
			json_dump = processor.get_json()
			open("%s.json" % args.thread, "w").write(json_dump)
		if args.txt:
			# store a rendered text file to `thread_id`.txt
			text_dump = processor.get_txt()
			open("%s.txt" % args.thread, "w").write(text_dump)
		if args.html:
			# store a rendered html page to `thread_id`.html
			html_dump = processor.get_html()
			open("%s.html" % args.thread, "w").write(html_dump)


if __name__ == "__main__":
	mane()
