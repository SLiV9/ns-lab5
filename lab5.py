## Netwerken en Systeembeveiliging Lab 5 - Distributed Sensor Network
## NAME: Sander in 't Veld
## STUDENT ID: 10277935
import sys
import struct
import select
from socket import *
from random import randint
from gui import MainWindow
from sensor import *


# Get random position in NxN grid.
def random_position(n):
	x = randint(0, n)
	y = randint(0, n)
	return (x, y)


def main(mcast_addr,
	sensor_pos, sensor_range, sensor_val,
	grid_size, ping_period):
	"""
	mcast_addr: udp multicast (ip, port) tuple.
	sensor_pos: (x,y) sensor position tuple.
	sensor_range: range of the sensor ping (radius).
	sensor_val: sensor value.
	grid_size: length of the  of the grid (which is always square).
	ping_period: time in seconds between multicast pings.
	"""
	# -- Create the multicast listener socket. --
	mcast = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)
	# Sets the socket address as reusable so you can run multiple instances
	# of the program on the same machine at the same time.
	mcast.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
	# Subscribe the socket to multicast messages from the given address.
	mreq = struct.pack('4sl', inet_aton(mcast_addr[0]), INADDR_ANY)
	mcast.setsockopt(IPPROTO_IP, IP_ADD_MEMBERSHIP, mreq)
	mcast.bind(mcast_addr)

	# -- Create the peer-to-peer socket. --
	peer = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)
	# Set the socket multicast TTL so it can send multicast messages.
	peer.setsockopt(IPPROTO_IP, IP_MULTICAST_TTL, 5)
	# Bind the socket to a random port.
	if sys.platform == 'win32': # windows special case
		peer.bind( ('localhost', INADDR_ANY) )
	else: # should work for everything else
		peer.bind( ('', INADDR_ANY) )

	# -- make the gui --
	window = MainWindow()
	window.writeln( 'my address is %s:%s' % peer.getsockname() )
	window.writeln( 'my position is (%s, %s)' % sensor_pos )
	window.writeln( 'my sensor value is %s' % sensor_val )

	# -- This is the event loop. --
	while window.update():
		line = window.getline()
		if (line):
			window.writeln("> " + line);
			
			#switch line
			if (line == "ping"):
				msg = message_encode(MSG_PING, 0, sensor_pos, sensor_pos)
				peer.sendto(msg, mcast_addr)
			elif (line == "list"):
				window.writeln("(not yet implemented)")
			elif (line == "move"):
				sensor_pos = random_position(grid_size)
				window.writeln( 'my new position is (%s, %s)' % sensor_pos )
			elif (line == "value"):
				window.writeln("(not yet implemented)")
			elif (line == "echo"):
				window.writeln("(not yet implemented)")
			elif (line == "size"):
				window.writeln("(not yet implemented)")
			elif (line == "sum"):
				window.writeln("(not yet implemented)")
			elif (line == "max"):
				window.writeln("(not yet implemented)")
			elif (line == "min"):
				window.writeln("(not yet implemented)")
			else:
				window.writeln("{ command not recognised }")
			#end switch line
		#end if line
		
		rrdy, wrdy, err = select.select([mcast], [], [], 0)
		for r in rrdy:
			(msg, addr) = r.recvfrom(256)
			if (len(msg) > 0):
				content = message_decode(msg)
				window.writeln("< " + str(addr) + ": " + str(content))
			#end if len
		#end for r
		
	#end while update
	return

# -- program entry point --
if __name__ == '__main__':
	import sys, argparse
	p = argparse.ArgumentParser()
	p.add_argument('--group', help='multicast group', default='224.1.1.1')
	p.add_argument('--port', help='multicast port', default=50000, type=int)
	p.add_argument('--pos', help='x,y sensor position', default=None)
	p.add_argument('--grid', help='size of grid', default=100, type=int)
	p.add_argument('--range', help='sensor range', default=50, type=int)
	p.add_argument('--value', help='sensor value', default=-1, type=int)
	p.add_argument('--period', help='period between autopings (0=off)',
		default=5, type=int)
	args = p.parse_args(sys.argv[1:])
	if args.pos:
		pos = tuple( int(n) for n in args.pos.split(',')[:2] )
	else:
		pos = random_position(args.grid)
	if args.value >= 0:
		value = args.value
	else:
		value = randint(0, 100)
	mcast_addr = (args.group, args.port)
	main(mcast_addr, pos, args.range, value, args.grid, args.period)

