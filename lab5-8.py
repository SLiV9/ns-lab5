## Netwerken en Systeembeveiliging Lab 5 - Distributed Sensor Network
## NAME: Sander in 't Veld
## STUDENT ID: 10277935
import sys
import struct
import select
import time
from socket import *
from random import randint
from gui import MainWindow
from sensor import *

# Get random position in NxN grid.
def random_position(n):
	x = randint(0, n)
	y = randint(0, n)
	return (x, y)
	
# Returns true if pos is in range of origin.
def is_in_range(origin, ran, pos):
	ox, oy = origin
	px, py = pos
	dx = ox - px
	dy = oy - py
	return (dx * dx + dy * dy <= ran * ran)


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
	
	# Periodic pinging.
	lastpingtime = -1
	
	# The set of neighbours; (position, address).
	neighbours = set()
	
	# Echo sequence number.
	echoseq = -1;
	
	# The dictionary of fathers of currently active echo's; (position, address).
	father = {}
	# The dictionary of sets of neighbours of currently active echo's.
	echo = {}
	# The dictionary of operations of currently active echo's.
	echoop = {}
	# The dictionary of lists of loads of currently active echo's.
	echoload = {}

	# -- This is the event loop. --
	while window.update():
		line = window.getline()
			
		newechoop = -1
		
		if (line):
			window.writeln("> " + line)
			
			#switch line
			if (line == "ping"):
				lastpingtime = -1
			elif (line == "list"):
				window.writeln("Neighbours:")
				for (npos, naddr) in neighbours:
					window.writeln("\t- neighbour at " + str(npos) + " from " + str(addr))
				#end for neighbours
				window.writeln("\t(end of list)")
			elif (line == "move"):
				sensor_pos = random_position(grid_size)
				window.writeln( 'my new position is (%s, %s)' % sensor_pos )
			elif (line == "value"):
				sensor_val = randint(0, 100)
				window.writeln( 'my sensor value is %s' % sensor_val )
			elif (line == "echo"):
				newechoop = OP_NOOP
			elif (line == "size"):
				newechoop = OP_SIZE
			elif (line == "sum"):
				newechoop = OP_SUM
			elif (line == "max"):
				newechoop = OP_MAX
			elif (line == "min"):
				newechoop = OP_MIN
			else:
				window.writeln("{ command not recognised }")
			#end switch line
		#end if line
		
		if ((lastpingtime < 0) or (ping_period > 0 and \
						(time.time() >= lastpingtime + ping_period))):
			neighbours.clear()
			msg = message_encode(MSG_PING, 0, sensor_pos, sensor_pos)
			peer.sendto(msg, mcast_addr)
			lastpingtime = time.time()
		#end if ping
		
		if (newechoop >= 0):
			echoseq += 1;
			eid = (sensor_pos, echoseq)
			echo[eid] = neighbours.copy()
			father[eid] = (sensor_pos, None)
			echoop[eid] = newechoop
			echoload[eid] = []
			msg = message_encode(MSG_ECHO, echoseq, sensor_pos, sensor_pos, newechoop)
			for (npos, naddr) in neighbours:
				peer.sendto(msg, naddr)
			#end for neighbours
		#end if echoop
		
		rrdy, wrdy, err = select.select([mcast, peer], [], [], 0)
		for r in rrdy:
			(msg, addr) = r.recvfrom(message_length)
			
			if (len(msg) > 0):
				content = message_decode(msg)
				tp, seq, initiator, sender, op, payload = content
				if (tp == MSG_PING):
					if (sender != sensor_pos):
						resp = message_encode(MSG_PONG, 0, sensor_pos, sensor_pos)
						peer.sendto(resp, addr)
					#end if notself
				elif (tp == MSG_PONG):
					if (is_in_range(sensor_pos, sensor_range, initiator)):
						neighbours.add((initiator, addr))
					#end if inrange
				elif (tp == MSG_ECHO):
					eid = (initiator, seq)
					if (eid not in echo):
						echo[eid] = neighbours.copy()
						echoop[eid] = op
						echoload[eid] = []
						frw = message_encode(MSG_ECHO, seq, initiator, sensor_pos, op) 
						for (npos, naddr) in echo[eid]:
							if (npos == sender):
								father[eid] = (npos, naddr)
							else:
								peer.sendto(frw, naddr)
							#end if sender
						#end for echo neighbours
						echo[eid].remove(father[eid])
					else:
						frw = message_encode(MSG_ECHO_REPLY, seq, initiator, sensor_pos, \
																	OP_NOOP)
						for (npos, naddr) in neighbours:
							if (npos == sender):
								peer.sendto(frw, naddr)
							#end if sender
						#end for neighbours
					#end if new echo
				elif (tp == MSG_ECHO_REPLY):
					eid = (initiator, seq)
					if (eid in echo):
						for (npos, naddr) in echo[eid]:
							if (npos == sender):
								gotfrom = (npos, naddr)
							#end if sender
						#end for echo neighbours
						if (op == echoop[eid]):
							echoload[eid].append(payload)
						#end if op match
						echo[eid].remove(gotfrom)
					#end if echo exists
				else:
					window.writeln("{ unknown message type " + str(tp) + " }")
				#end switch tp
				window.writeln("< " + str(addr) + ": " + str(content))
			#end if len
		#end for r
		
		finished = set()
		for (eid, pending) in echo.iteritems():
			if (len(pending) == 0):
				op = echoop[eid]
				if (op == OP_NOOP or op == OP_SIZE):
					echoload[eid].append(1)
				elif (op == OP_SUM or op == OP_MIN or op == OP_MAX):
					echoload[eid].append(sensor_val)
				#end switch op
				
				if (op == OP_SIZE or op == OP_SUM):
					load = sum(echoload[eid])
				elif (op == OP_MIN):
					load = min(echoload[eid])
				elif (op == OP_MAX):
					load = max(echoload[eid])
				else:
					load = 0
				#end switch op
				
				finished.add(eid)
				(fpos, faddr) = father[eid]
				if (faddr is None):
					if (op == OP_SIZE):
						window.writeln("Cluster size: " + str(load))
					elif (op == OP_SUM):
						window.writeln("Sum of sensor values in cluster: " + str(load))
					elif (op == OP_MIN):
						window.writeln("Minimum of sensor values in cluster: " + str(load))
					elif (op == OP_MAX):
						window.writeln("Maximum of sensor values in cluster: " + str(load))
					else:
						window.writeln("Echo complete.")
					#end switch op
				else:
					(initiator, seq) = eid
					msg = message_encode(MSG_ECHO_REPLY, seq, initiator, sensor_pos, \
															op, load) 
					peer.sendto(msg, faddr)
				#end if self father
			#end if echo empty
		#end for echos
		for eid in finished:
			del echo[eid]
			del father[eid]
			del echoop[eid]
			del echoload[eid]
		#end for finished
		
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

