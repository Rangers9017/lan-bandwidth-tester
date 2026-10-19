# LAN Bandwidth Tester

A small Tkinter desktop app that measures TCP throughput between two computers by sending a stream of random data.

## How to use

1. Run `python gigabit_tester.py` on both computers.
2. On the first computer, choose **server** mode and start listening on port `5201`.
3. On the second computer, choose **client** mode, enter the server computer's private IP address, and start the test.
4. Review the average throughput and amount of data transferred.

The default test duration is 10 seconds. Both computers need Python 3 and Tkinter; the app uses only the Python standard library.

## Türkçe

İki bilgisayar arasında TCP üzerinden veri göndererek yerel ağ aktarım hızını ölçen küçük bir Tkinter uygulamasıdır. Bir bilgisayarda sunucu modunu, diğerinde istemci modunu açın; istemciye sunucunun yerel IP adresini girin.

## Network safety

The server listens on all network interfaces at the selected port (5201 by default), and the protocol has no authentication or encryption. Use it only on a trusted network with devices you own or are authorized to test. Allow the port only on a private network in your firewall, and do not forward it from your router or expose it to the public internet. This measures a connection between two computers; it is not an internet speed test.
