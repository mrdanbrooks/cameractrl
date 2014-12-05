Cameractrl
=====

Mochad X10 Client to wirelessly control a Motion camera 

Installation
------------

The following instructions are for installing on debian systems.

Install twisted framework

```
sudo apt-get install python-twisted
```

Install cameractrl.py

```
sudo cp /usr/local/bin/cameractrl.py /usr/local/bin/cameractrl.py
sudo chmod 755 /usr/local/bin/cameractrl.py
```

Install sysvinit rules

```
sudo cp etc/init.d/cameractrl /etc/init.d/cameractrl
sudo chmod 755 /etc/init.d/cameractrl
sudo update-rc.d cameractrl defaults
```

