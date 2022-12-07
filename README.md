# metermaid

🎵Lovely Rita…🎵

Read images of a gas meter. Chart usage.

### capture images from a video stream
```bash
nohup ffmpeg -y -i "rtsp://$VIDEO_HOST:554/user=$VIDEO_USER&password$VIDEO_PASSWORD=&channel=$VIDEO_CHANNEL&stream=$VIDEO_STREAM.sdp?real_stream--rtp-caching=100" -r 0.1 -strftime 1 "$IMAGE_DIR/gas-meter-%Y-%m-%d_%H-%M-%S.jpg" &
```

### translate raw image into machine-readable data snapshot
```bash
python3 read_meter_images.py noop $IMAGE_DIR/gas-meter-????-??-??_??-??-??.jpg 2>/dev/null | tee test-set-2.ndjson
```


### create time series from incremental use
```bash
python3 process_series.py test-set-2.ndjson | tee test-set-2.rates.ndjson
```