#!/bin/bash
cd "$(cd -P -- "$(dirname -- "$0")" && pwd -P)"
nosetests --with-gae --gae-lib-root /usr/local/google_appengine
