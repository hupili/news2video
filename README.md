# news2video

Demo link: https://www.youtube.com/watch?v=W9z9JduEzbI

* Convert a news article to video with Cantonese narrative
* Convert a news article to video with Mandarin narrative

## Requirements

* ffmpeg
* sox
* imagemagick
* avconv

On OS X, you can:

```
brew install sox imagemagick libav libass ffmpeg
```

## Python 3

* `virtualenv -p python3 venv`, or `pyvenv venv`.
* `source venv/bin/activate`
* `pip install -r requirements.txt`

Caveats:

* You may want to use `pip install -r requirements.txt --ignore-installed`. See [this issue](https://github.com/pypa/pip/issues/333)
* Or, you may want to start fresh. `pip install -r requirements.txt --ignore-installed --no-cache-dir`
* Or, you may want to start fresh. `pip3 install -r requirements.txt --ignore-installed --no-cache-dir`

## Test pages

* <http://project.initiumlab.com/news2video/case1/>

