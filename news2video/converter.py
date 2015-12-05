import requests
from readability.readability import Document
import pandas as pd
import bs4
from bs4 import Tag, BeautifulSoup
import hashlib
import os
from os import path
import sh


class Extractor(object):
    """
    Extract text/ images sequences from a web page's main body
    """
    def __init__(self, base_url):
        self.cur_text = ''
        self.result = []
        self.base_url = base_url

    def get_abs_url(self, url):
        if url.startswith('http://') or url.startswith('https://'):
            return url
        else:
            return '%s/%s' % (self.base_url, url)

    def recursive_extract_text_image(self, obj):
        # reference:
        # http://stackoverflow.com/questions/20590624/python-beautifulsoup-div-text-and-img-attributes-in-correct-order
        for child in obj.children:
            if isinstance(child, Tag):
                #result.append(child.get('alt', ''))
                self.recursive_extract_text_image(child)
                if child.name == 'img':
                    self.result.append(('text', self.cur_text))
                    self.cur_text = ''
                    self.result.append(('image',
                                        self.get_abs_url(child['src'])
                    ))
            else:
                if len(child.strip()) > 0:
                    self.cur_text += ' ' + child.strip() + ' '

    def html_to_asset_list(self, html):
        """
        :param html: The html content in str
        :return: The extracted list of text/ image sequence
        """
        bs_obj = BeautifulSoup(html, 'html.parser')
        self.result = []
        self.cur_text = ''
        self.recursive_extract_text_image(bs_obj)
        self.result.append(('text', self.cur_text))
        return self.result


class Converter(object):
    def __init__(self):
        pass

    def string2hash(self, s):
        m = hashlib.sha256()
        m.update(s.encode('utf-8'))
        return m.hexdigest()[:16]

    def get_audio_length(self, local_src):
        filename = local_src + '.wav'
        # Caveats: can only deal with < 60s audios
        # | grep Duration | cut -f1 -d, | cut -f4 -d:
        seconds = sh.soxi('-D', filename)
        return seconds.strip()

    def convert(self, url, fn_output):
        # Download webpage
        res = requests.get(url)
        html = res.content.decode('utf-8')

        # Analyze basic sequence
        readable_article = Document(html).summary()
        base_url = path.dirname(res.request.url)
        result = Extractor(base_url).html_to_asset_list(readable_article)
        #print(result)
        df_screenplay = pd.DataFrame(result, columns=['type', 'content'])
        df_screenplay['local_src'] = df_screenplay['content'].apply(lambda x: self.string2hash(x))
        image_selector = (df_screenplay['type'] == 'image')
        df_screenplay.loc[image_selector, 'filename'] = df_screenplay.loc[
            image_selector, 'content'].apply(lambda x: path.basename(x))
        df_screenplay.loc[image_selector, 'extname'] = df_screenplay.loc[
            image_selector, 'filename'].apply(lambda x: path.splitext(x)[1])
        df_screenplay = df_screenplay.fillna('')
        df_screenplay['download_name'] = df_screenplay['local_src'] + df_screenplay['extname']
        df_screenplay['converted_name'] = df_screenplay['local_src'] + '.png'


        # Download images and convert to .png
        commands = []
        for (i, r) in df_screenplay.iterrows():
            if r['type'] == 'image':
                commands.append('wget {content} -O {download_name}'.format(**r))
        for (i, r) in df_screenplay.iterrows():
            if r['type'] == 'image':
                commands.append('convert {download_name} {converted_name}'.format(**r))
        for c in commands:
            os.system(c)

        # Generate audio via say (m4a) and convert to (wav)
        commands = []
        for (i, r) in df_screenplay.iterrows():
            if r['type'] == 'text':
                #commands.append('say --output-file={local_src}.m4a --voice=daniel --rate=220 --progress --file-format=m4af "{content}"'.format(**r))
                #commands.append('say --output-file={local_src}.m4a -v Ting-Ting --rate=300 --progress --file-format=m4af "{content}"'.format(**r))
                commands.append('say --output-file={local_src}.m4a -v Sin-ji --rate=200 --progress --file-format=m4af "{content}"'.format(**r))
        for (i, r) in df_screenplay.iterrows():
            if r['type'] == 'text':
                commands.append('avconv -i {local_src}.m4a -y {local_src}.wav'.format(**r))
        for c in commands:
            os.system(c)

        # Analyze audio duration
        text_selector = (df_screenplay['type'] == 'text')
        df_screenplay.loc[text_selector, 'duration'] = df_screenplay.loc[text_selector, 'local_src'].apply(self.get_audio_length)

        # Organise scenes
        scenes = []
        df_sp_orged = df_screenplay.reset_index()
        # Group the sequence
        df_sp_orged['group'] = df_sp_orged['index'].apply(lambda x: int((x + 1) / 2))
        for (gname, group) in df_sp_orged.groupby('group'):
            if len(group[group['type'] == 'image']) == 0:
                fn_image = 'default-image.png'
            else:
                fn_image = group[group['type'] == 'image']['converted_name'].values[0]

            if len(group[group['type'] == 'text']) == 0:
                duration = 1.53
                fn_audio = 'default-audio.mp4'
            else:
                duration = group[group['type'] == 'text']['duration'].values[0]
                fn_audio = group[group['type'] == 'text']['local_src'].values[0] + '.m4a'
            scenes.append(('%04d' % gname, fn_image, duration, fn_audio))
        df_scenes = pd.DataFrame(scenes, columns=['group', 'fn_image', 'duration', 'fn_audio'])

        # Final assemble of the video
        os.system('cp -f default/* .')
        df_scenes['fn_video_only'] = 'group' + df_scenes['group'] + '.mp4'
        df_scenes['fn_video'] = 'group' + df_scenes['group'] + '-a.mp4'
        # Following was used to solve non integer fps problem the conflicts with stanrdard
        # Now we already use output parameter to work around.
        #df_scenes['duration'] = df_scenes['duration'].apply(lambda x: int(np.ceil(float(x))))
        df_scenes['fn_image_resized'] = 'resized-' + df_scenes['fn_image']
        df_scenes['fn_audio_only'] = 'group' + df_scenes['group'] + '-audio.m4a'

        # To avoid too short clips
        df_scenes = df_scenes[df_scenes['duration'].apply(lambda x: float(x) > 0.1)]
        commands = []
        for (i, r) in df_scenes.iterrows():
            commands.append('cp {fn_audio} {fn_audio_only}'.format(**r))
        commands
        for c in commands:
            os.system(c)
            commands = []
        for (i, r) in df_scenes.iterrows():
            commands.append('convert {fn_image} -resize 600x400! {fn_image_resized}'.format(**r))
        print(commands)
        for c in commands:
            os.system(c)
        commands = []
        for (i, r) in df_scenes.iterrows():
            commands.append('ffmpeg -f image2 -r 1/{duration} -i {fn_image_resized} -qscale:v 1 -copyts -vcodec mpeg4 -y -r 25 {fn_video_only}'.format(**r))
        for (i, r) in df_scenes.iterrows():
            commands.append('ffmpeg -i {fn_video_only} -i {fn_audio} -qscale:v 1 -copyts -vcodec copy -acodec copy -y {fn_video}'.format(**r))
            #commands.append('ffmpeg -i {fn_video_only} -i {fn_audio} -map 0:0 -map 1 -vcodec copy -acodec copy -y {fn_video}'.format(**r))
        commands
        for c in commands:
            os.system(c)
        open('playlist.txt', 'w').write('\n'.join(list(df_scenes['fn_video'].apply(lambda x: "file '%s'" % x))))
        os.system('ffmpeg -f concat -i playlist.txt -c copy -y %s' % fn_output)

if __name__ == '__main__':
    import sys
    url = sys.argv[1]
    fn_output = sys.argv[2]
    Converter().convert(url, fn_output)
