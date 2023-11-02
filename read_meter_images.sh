#!/bin/bash

ls -1 ./raw-images/ | cut -c 1-20 | grep gas-meter | uniq | while read FILE_PREFIX; do 
	echo "working on $FILE_PREFIX"
	python3 read_meter_images.py archive --archive_dir archived-images/  ./raw-images/$FILE_PREFIX* >> readings/readings.$FILE_PREFIX.ndjson
done
