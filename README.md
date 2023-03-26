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

### where to get weather data
https://www.ncei.noaa.gov/access/search/data-search/global-hourly?bbox=43.035,-78.917,42.860,-78.624&pageNum=1&startDate=2022-12-01T00:00:00&endDate=2023-01-01T23:59:59


### integration process
```bash
# weather
for YEAR in 2022 2023; do
  ls -1 weather-data-ncei/72528014733-$YEAR* | tail -n1 | while read FILE; do python3 decode_metar_weather_data.py ndjson <(csv2ndjson $FILE) > weather-data-ncei/hourly-temps-$YEAR.latest.ndjson; done
done
cat weather-data-ncei/hourly-temps-202?.latest.ndjson > weather-data-ncei/hourly-temps.all.ndjson

#remote reading image processing
nohup ls -1 ./raw-images/ | cut -c 1-20 | grep gas-meter | uniq | while read FILE_PREFIX; do echo "working on $FILE_PREFIX"; python3 read_meter_images.py archive --archive_dir archived-images/  ./raw-images/$FILE_PREFIX* >> readings/readings.$FILE_PREFIX.ndjson; done

#local reading transfer
rsync --progress -v 192.168.4.85:/home/mkomorowski/repos/metermaid/readings/readings.gas-meter-* readings/

#generate rates
ls -1 readings/*.ndjson | while read FILE; do echo "processing $FILE" 1>&2; python3 process_series.py $FILE; done > rates/rates.all.ndjson && wc rates/rates.all.ndjson

#generate hourlies
cat rates/rates.all.ndjson | ndjson-reduce 'p[d.hour]=(p[d.hour] || 0) + d.delta, p' '{}' | ndjson-map 'Object.keys(d).map(key=>({"hour":key, "cf":d[key]}))' | ndjson-split > hourlies/hourly.all.ndjson

#join weather and hourly data
ndjson-join d.hour d.hour  weather-data-ncei/hourly-temps.all.ndjson hourlies/hourly.all.ndjson | ndjson-map 'd[0].cf=d[1].cf, d[0]' > hourlies/hourly.all.with-outside-temp.ndjson
```
