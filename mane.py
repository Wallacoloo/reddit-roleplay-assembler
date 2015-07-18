#!/usr/bin/python

# Requirements: install Python Reddit API Wrapper (PRAW)
# Do so via `pip install praw` or download from github: https://github.com/praw-dev/praw

# This script reads through a reddit thread, finds the deepest comment, and walks down the chain to it,
# Compiling all comments in that chain into a single page.
# This is good for things like role-playing where everything is supposed to happen chronologically 
#   and the number of comments grows absurdly.


import praw, itertools, sys, json


def reverse_enumerate(iterable):
    """
    Enumerate over an iterable in reverse order while retaining proper indexes
    """
    # Lifted from http://galvanist.com/post/53478841501/python-reverse-enumerate
    return itertools.izip(reversed(xrange(len(iterable))), reversed(iterable))

def max_comment_depth(comment, cur_depth=0):
	"""
	Given a comment, find the maximum depth of its descendents
	"""
	replies = comment.replies if isinstance(comment, praw.objects.Comment) else \
		(comment.comments if isinstance(comment, praw.objects.Submission) else None)
	if replies:
		return max(max_comment_depth(reply, cur_depth+1) for reply in replies)
	else:
		return cur_depth

def filter_comments_by_max_depth(comments, max_depth):
	"""
	Delete all comments which don't have any descendents at depths >= max_depth
	"""
	for i, c in reverse_enumerate(comments):
		# If the comment has no children at a sufficient depth, delete it altogether,
		# Else apply the same algorithm to its children
		if max_comment_depth(c) < max_depth-1:
			del comments[i]
		elif isinstance(c, praw.objects.Comment):
			filter_comments_by_max_depth(c.replies, max_depth-1)

def flatten_mono_thread(comment):
	"""
	Flattens a chain of comments,
	but stops if it gets to an ambiguous point where a comment has more than one child (or no children)
	"""
	while isinstance(comment, praw.objects.Comment) and len(comment.replies) == 1:
		yield comment
		comment = comment.replies[0]

def serialize_thread_to_json(comments):
	"""
	Serialize a flat sequence of comments into JSON format.
	"""
	list_of_dicts = [{ "author": c.author.name, "body_html":c.body_html, 
	"created_utc":c.created_utc, "permalink":c.permalink } for c in comments]
	return json.dumps(list_of_dicts)

def mane(thread_id):
	"""
	thread_id is the id of the reddit submission to squash (check the URL).
	author_map is an optional dictionary to map reddit usernames to character names.
	Function finds the longest string of comments and squashes them to plaintext of the from
	<character_name>: <message>
	<character_name>: <message>
	[...]
	"""
	# Create a context through which to access reddit
	reddit = praw.Reddit(user_agent='github.com/wallacoloo/reddit-roleplay-assembler')
	thread = reddit.get_submission(submission_id=thread_id)

	# Many functions recurse through the comment chain, so set a high recursion limit
	sys.setrecursionlimit(5*thread.num_comments+1000)

	# Expand all comments (this will take some time!)
	thread.replace_more_comments(limit=None, threshold=1)

	# Remove all but the main thread of comments
	max_depth = max_comment_depth(thread)
	filter_comments_by_max_depth(thread.comments, max_depth)

	# There may still be comment forks near the end that have the same length
	# We need to drop everything after the fork, as we don't know which of the choices is the main discussion
	flattened = flatten_mono_thread(thread.comments[0])
	return serialize_thread_to_json(flattened)

if __name__ == "__main__":
	print mane(thread_id="339wbs")