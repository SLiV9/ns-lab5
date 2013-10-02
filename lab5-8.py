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
	
	# Periodic pinging. A value of -1 causes an immediate ping event.
	# When entering the group, a first ping is sent.
	lastpingtime = -1
	
	# The set of neighbours; (position, address).
	neighbours = set()
	
	# The echo sequence number.
	echoseq = -1;
	
	# The dictionary of fathers of currently active echo's; (position, address).
	father = {}
	# The dictionary of sets of pending neighbours of currently active echo's.
	echo = {}
	# The dictionary of operations of currently active echo's.
	echoop = {}
	# The dictionary of lists of loads of currently active echo's.
	echoload = {}

	# -- This is the event loop. --
	while window.update():
		line = window.getline()
		
		# Our event loop will consist of 5 steps.
		# 1: Interpret the command line input (if any).
		# 2: If a ping event should occur, ping.
		# 3: If an echo event should occur, echo.
		# 4: If one or more messages are received, handle them.
		# 5: If echo's have finished, show or forward their results.
		
		# The operation of a new echo. If the value is nonnegative, an echo occurs.
		newechoop = -1
		
		if (line):
			#debug: window.writeln("> " + line)
			
			#switch line
			if (line == "ping"):
				# Cause a ping event immediately.
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
		
		# If lastpingtime has a negative value, a ping occurs.
		# Otherwise, a ping occurs if periodic pinging is on and ping_period
		# seconds have past since the last ping.
		# Any ping sets the timer back to ping_period seconds.
		if ((lastpingtime < 0) or (ping_period > 0 and \
						(time.time() >= lastpingtime + ping_period))):
			neighbours.clear()
			msg = message_encode(MSG_PING, 0, sensor_pos, sensor_pos)
			peer.sendto(msg, mcast_addr)
			lastpingtime = time.time()
		#end if ping
		
		# If newechoop has a nonnegative value, a new echo wave is sent.
		# echo[eid] is the set of all neighbours that haven't responded yet.
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
		
		# Read from available sockets.
		rrdy, wrdy, err = select.select([mcast, peer], [], [], 0)
		for r in rrdy:
			(msg, addr) = r.recvfrom(message_length)
			
			if (len(msg) > 0):
				content = message_decode(msg)
				tp, seq, initiator, sender, op, payload = content
				
				# Take actions depending on the message type (tp).
				
				if (tp == MSG_PING):
					# Respond to pings with a pong with your position.
					# Don't respond to your own pings.
					if (sender != sensor_pos):
						resp = message_encode(MSG_PONG, 0, initiator, sensor_pos)
						peer.sendto(resp, addr)
					#end if notself
					
				elif (tp == MSG_PONG):
					if (is_in_range(sensor_pos, sensor_range, sender)):
						neighbours.add((sender, addr))
					#end if inrange
					
				elif (tp == MSG_ECHO):
					eid = (initiator, seq)
					if (eid not in echo):
						# If this echo is new, make a new (sub)echo.
						# echo[eid] is the set of neighbours that haven't responded yet.
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
						
						# We're not waiting for the father to respond, so remove it.
						echo[eid].remove(father[eid])
						
					else:
						# If you already received this echo, respond with empty payload
						# and set operation to OP_NOOP, to prevent the payload from being
						# registered as value 0.
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
						
						# Add the payload to the echoload list. If the echo operation is a
						# real operation, discard any payloads that arrive with operation
						# OP_NOOP; these are just acknowledgements.
						if (op == echoop[eid]):
							echoload[eid].append(payload)
						#end if op match
						
						# gotfrom has responded; remove it from the echo's pending set.
						echo[eid].remove(gotfrom)
					#end if echo exists
					
				else:
					window.writeln("{ unknown message type " + str(tp) + " }")
				#end switch tp
				window.writeln("< " + str(addr) + ": " + str(content))
			#end if len
		#end for r
		
		# We shall check if any (sub)echo's are finished, i.e. all neighbours that
		# should have responded, have responded. If so, echo[eid] will be empty.
		finished = set()
		for (eid, pending) in echo.iteritems():
			if (len(pending) == 0):
				finished.add(eid)
			
				# If the operation is a simple count, add a 1 to the list.
				# If the operation manages sensor values, add your own sensor value.
				op = echoop[eid]
				if (op == OP_NOOP or op == OP_SIZE):
					echoload[eid].append(1)
				elif (op == OP_SUM or op == OP_MIN or op == OP_MAX):
					echoload[eid].append(sensor_val)
				#end switch op
				
				# If the operation is a function on payloads, calculate the result.
				# If the operation is a basic echo, ignore the payloads; the fact that
				# the echo completes is enough information.
				if (op == OP_SIZE or op == OP_SUM):
					result = sum(echoload[eid])
				elif (op == OP_MIN):
					result = min(echoload[eid])
				elif (op == OP_MAX):
					result = max(echoload[eid])
				else:
					result = 1
				#end switch op
				
				(fpos, faddr) = father[eid]
				# If I am the initiator, faddr will be set to None.
				# Otherwise, faddr will be the address of the father.
				
				if (faddr is None):
					# If I am the initiator, display the results.
					if (op == OP_SIZE):
						window.writeln("Cluster size: " + str(result))
					elif (op == OP_SUM):
						window.writeln("Sum of sensor values in cluster: " \
															+ str(result))
					elif (op == OP_MIN):
						window.writeln("Minimum of sensor values in cluster: " \
															+ str(result))
					elif (op == OP_MAX):
						window.writeln("Maximum of sensor values in cluster: " \
															+ str(result))
					else:
						window.writeln("Echo complete.")
					#end switch op
					
				else:
					# If I am not the father, forward the subresult to the father.
					(initiator, seq) = eid
					msg = message_encode(MSG_ECHO_REPLY, seq, initiator, sensor_pos, \
															op, result)
					peer.sendto(msg, faddr)
				#end if self father
			#end if echo empty
		#end for echos
		
		# Remove finished echo's.
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

