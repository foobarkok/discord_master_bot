pip install -r requirements.txt

mkdir -p bin
curl -L https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz | tar -xJ --strip-components=2 -C bin --wildcards '*/bin/ffmpeg' '*/bin/ffprobe'
chmod +x bin/ffmpeg bin/ffprobe
