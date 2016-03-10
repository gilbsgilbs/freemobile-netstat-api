FreeMobile Netstat API
======================
Brief
-----
This project is aimed at aggregating FreeMobile Netstat Android app statistics over a REST API.

How to install
--------------
You will need Python 3.4.1+ and the following system dependencies:

```
sudo apt-get install build-essential libpython3.4-dev libmemcached-dev zlib1g-dev memcached mongodb
```

Unfortunately, I didn't take time to provide a proper setup.py install, hence the install process is a bit manual. Do not
hesitate to contribute to improve this.

```
virtualenv -p /usr/bin/python3.4 venv
. ./venv/bin/activate
pip install -r requirements.txt
```

You can then run the run.py file, and that's it.

```
python3.4 run.py
```

You can start contributing ;) .

Contributors
------------
- gilbsgilbs
- Pixmob ([original JAVA API + static web](https://github.com/pixmob/freemobilenetstat-gae))

