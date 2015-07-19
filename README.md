# Reddit Roleplay Assembler
This tool takes a reddit thread, finds the longest chain of comments, and then flattens that chain into something
that's easy to read.

Any comments that aren't directly a part of the longest chain are discarded.

Why?
--------
Reddit will only show comments down a depth of 10 before forcing you to click to load 
the next 10 comments. For most threads, this isn't much of an issue, but for threads with 
lots of back-and-forth, which is especially common in role-playing, the chain of comments 
can easily reach into the thousands and reloading after reading each 10 can get tiring.

Also, this gives an easy way to save a thread for offline reading.

Render formats
--------

Reddit Roleplay Assembler (RRA) can currently export the flattened comments to JSON format or plaintext.

In [JSON](https://en.wikipedia.org/wiki/JSON) format, the decoded data is a flat array of dictionaries,
where each dictionary represents a single comment and the comments are ordered chronologically in the array.
Each comment looks like this (for example):
```json
{
  "author": "wallacoloo",
  "body_html": "Have you seen the <a href='https://github.com/Wallacoloo/reddit-roleplay-assembler'>Reddit Roleplay Assembler</a>?",
  "created_utc": 1437126303.0,
  "permalink": "https://www.reddit.com/r/..."
}
```

In plaintext, all the text is extracted from the body of each comment and the comments are rendered like:
```
<author>: body
```
and with a blank line between each comment (the above angle brackets *are* included in the plaintext). 
When it comes to links, the URL is stripped but the link description is preserved.

Usage
--------

This script is designed to be run from a terminal as so:

```
mane.py --thread xxxxxx [--json] [--txt]
```

`xxxxxx` is the id of the thread you wish to flatten, and `--json` and `--txt` are flags to 
specify the desired output format. Output will be placed in a file of the same name as the thread id, 
but with a ".json" or ".txt" extension.

For example, if you wanted a plaintext version of the ridiculously long exchange between Lunas_Disciple and Dr_Zorand 
in this thread: https://www.reddit.com/r/mylittlepony/comments/339wbs/lets_raise_the_stakes_shall_we_by_inkygarden/cqivxk1,
you would take the thread id from that url, `339wbs`, run `mane.py --thread 339wbs --json --txt`,
and then view the output in `339wbs.txt`

If a file of the name "xxxxxx.json" already exists, this will be used as a cache when rendering other formats.
Therefore, it is recommended to always pass the `--json` flag when loading a thread for the first time,
as it can easily take upwards of an hour to download the thread if it contains 10000 comments 
(since reddit only lets one request 10 comments at a time, it becomes 1000 individual requests).
