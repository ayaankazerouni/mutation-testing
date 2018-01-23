./lib/distributed-map.pl \
  --cluster clusters.json \
  --workScript /home/ayaan/Developer/mutation-testing/run-mutation-test.js \
  --taskFile $1 \
  --env 'PATH=/home/ayaan/.nvm/versions/node/v8.9.4/bin/node:$PATH'
