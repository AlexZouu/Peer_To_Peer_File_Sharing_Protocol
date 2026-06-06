import argparse
import datetime
import random
import socket


BAD_CHANCE = 0.03            # The chance that something bad will happen (drop, corrupt, reorder)
REORDER_CHANCE = 0.3        # The chance that a reordered packet will be sent instead of a packet for forwarding
IP = '127.0.0.1'            # IP address of the server (same machine)
INTERMEDIARY_PORT = 1024   # Port of the intermediary program


def printT(message):
  """
  Prints a message with the time in HR:MIN:SEC appended in front

  Args:
    message (str): The message to print
  """
  currentTime = datetime.datetime.now().strftime("%H:%M:%S")
  print(f'{currentTime}\t|\t{message}')


def corruptDatagram(datagram):
  """
  Corrupts a datagram by flipping a bit

  Args:
    datagram (bytes): The datagram to corrupt
  
  Return:
    (bytes): The corrupted datagram
  """
  return (int.from_bytes(datagram) ^ 1).to_bytes(len(datagram))   # XORs the datagram with 1


def forward(drop, corrupt, reorder):
  """
  Forward datagrams to their correct destination

  Args:
    drop (bool): If true, drop the datagrams sometimes
    corrupt (bool): If true, corrupt the datagrams sometimes
    reorder (bool): If true, reorder packets sometimes
  """
  sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)   # Create the sockets
  sock.bind((IP, INTERMEDIARY_PORT))    # Bind it to the IP and port
  sock.setblocking(False)   # Set blocking to false so it doesn't block the program

  packetsToForward = []
  reorderedPackets = []

  while True:
    try:    # Try to receive data
      datagram, _ = sock.recvfrom(2048)

      sPort = int.from_bytes(datagram[0:2])
      dPort = int.from_bytes(datagram[2:4])   # Get the destination port
      seq = int.from_bytes(datagram[8:10]) + 1
      numPackets = int.from_bytes(datagram[12:14])

      printT(f'Received packet {seq}/{numPackets} from {sPort} for {dPort}')
      packetsToForward.append(datagram)
    except socket.error: pass   # No data was ready, so we ignore it


    if len(packetsToForward) > 0 or len(reorderedPackets) > 0:   # If there are packets to send
      datagram = None

      if len(reorderedPackets) == 0: datagram = packetsToForward.pop(0)   # If there are only packets to forward, just get the first packet from that list
      elif len(packetsToForward) == 0: datagram = reorderedPackets.pop(0)   # If there are only packets to reorder, just get the first packet from that list
      else:
        if random.random() < REORDER_CHANCE: datagram = reorderedPackets.pop(0)
        else: datagram = packetsToForward.pop(0)

      dport = int.from_bytes(datagram[2:4])   # Get the destination port
      
      if drop and random.random() < BAD_CHANCE:   # Attempt to drop the packet
        printT(f'Dropped packet for destination {dport}')
        continue
        
      if reorder and random.random() < BAD_CHANCE:    # Try to reorder the packet
        reorderedPackets.append(datagram)   # Add the packet to the list of packets that were reordered
        printT(f'Reordered packet for destination {dport}')
        continue

      if corrupt and random.random() < BAD_CHANCE:    # Try to corrupt the packet
        datagram = corruptDatagram(datagram)
        printT(f'Corrupted packet for destination {dport}')   # Attempt to drop the packet

      sock.sendto(datagram, (IP, dport))    # Send the packet
      printT(f'Forwarded packet to destination {dport}')


def parseArgs():
  """
  Handles reading in command line arguments

  Returns:
    args (argparse.Namespace): A dict of the command line arguments
  """
  parser = argparse.ArgumentParser()    # Create the parser

  percentage = round(BAD_CHANCE * 100)

  # Add all the args
  parser.add_argument('-d', help=f'Drop {percentage}% of the packets', action='store_true')
  parser.add_argument('-c', help=f'Corrupt {percentage}% of the packet', action='store_true')
  parser.add_argument('-r', help='Reorder the packets', action='store_true')

  args = parser.parse_args()    # Parse the args

  return args.d, args.c, args.r


def main():
  """
  The entry point to the program
  """
  drop, corrupt, reorder = parseArgs()
  forward(drop, corrupt, reorder)


if __name__ == '__main__': main()