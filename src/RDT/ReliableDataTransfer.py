import datetime
import math
import socket
import time


# ============================================================================================================
# Generic variables and helper functions
# ============================================================================================================


_CWND_SIZE = 10               # At most this many packets "in the air" at a time
_IP = '127.0.0.1'             # IP address of the server (same machine)
_INTERMEDIARY_PORT = 49998    # Port of the intermediary program
_TIMEOUT = 0.01               # Packet will be resent if an ACK isn't received in this many seconds
_CHUNK_SIZE = 2000            # The message will be chunked into bytes of this size
_RESET_TIME = _TIMEOUT * 100  # The number of seconds before the receiver will end after getting all packets
_HEADER_SIZE = 14             # The size of the packet header in bytes
_SPORT_HDR_LOC = 0            # The byte where the source port is located in the header
_DPORT_HDR_LOC = 2            # The byte where the destination port is located in the header
_LEN_HDR_LOC = 4              # The byte where the length of the header is located
_CHKSUM_HDR_LOC = 6           # The byte where the checksum is located in the header
_SEQ_HDR_LOC = 8              # The byte where the sequence number is located in the header
_ID_HDR_LOC = 10              # The byte where the ID is located in the header
_NUM_PKT_HDR_LOC = 12         # The byte where the number of packets is located in the header
_MSG_HDR_LOC = 14             # The byte where the message is located

debugMode = False


def _printT(message):
  """
  Prints a message with the time in HR:MIN:SEC appended in front

  Args:
    message (str): The message to print
  """
  if not debugMode: return

  currentTime = datetime.datetime.now().strftime("%H:%M:%S")
  print(f'{currentTime}\t|\t{message}')


def _calculateChecksum(packet):
  """
  Calculate the checksum of a given packet

  Args:
    packet (bytes): The packet to calculate the checksum of

  Returns:
    (int): The checksum of the packet
  """
  if len(packet) % 2 != 0: packet += b'\x00'    # If the packet is an odd number of bytes, add an empty byte

  checksum = 0

  for i in range(0, len(packet), 2):    # For every 2 bytes
    checksum += (packet[i] << 8) + packet[i + 1]    # Add the first byte shifted by 8 + the next byte
  
  checksum = (checksum >> 16) + (checksum & 0xFFFF)   # Handling extra bits
  checksum += (checksum >> 16)
  checksum = ~checksum & 0xFFFF

  return checksum


def _isValidDatagram(sPort, realID, datagram):
  """
  Determines if a datagram is valid by calculating the checksum and comparing it to the checksum in the packet

  Args:
    sPort (int): The port the packet should have come from
    realID (int): The ID that the packet should have
    datagram (bytes): The datagram to test validity of

  Returns:
    (bool): If the packet is valid
  """
  sourcePort = datagram[_SPORT_HDR_LOC:_DPORT_HDR_LOC]    # Get all the fields
  destinationPort = datagram[_DPORT_HDR_LOC:_LEN_HDR_LOC]
  pktLength = datagram[_LEN_HDR_LOC:_CHKSUM_HDR_LOC]
  checksum = datagram[_CHKSUM_HDR_LOC:_SEQ_HDR_LOC]
  seq = datagram[_SEQ_HDR_LOC:_ID_HDR_LOC]
  id = datagram[_ID_HDR_LOC:_NUM_PKT_HDR_LOC]
  numPackets = datagram[_NUM_PKT_HDR_LOC:_MSG_HDR_LOC]
  message = datagram[_MSG_HDR_LOC:]

  if id != realID.to_bytes(2): return False   # If the id is not equal to the ID it should be, return false
  if sPort and sPort.to_bytes(2) != sourcePort: return False    # If the source port doesn't match the source port it should be, return

  dummyPacket = sourcePort + destinationPort + pktLength + (0).to_bytes(2) + seq + id + numPackets + message    # Create dummy packet with checksum of 0

  calculatedChecksum = _calculateChecksum(dummyPacket)   # Calculate the checksum of the dummy packet

  return checksum == calculatedChecksum.to_bytes(2)   # Return true if calculated checksum matches checksum in packet

  
def _createPacket(sPort, dPort, seq, id, numPackets, message):
  """
  Create a packet

  Args:
    sPort (int): The source port
    dPort (int): The destination port
    seq (int): The sequence number of the packet
    id (int): The ID of the packet
    numPackets (int): The total number of packets the server should expect
    message (bytes): The message to send

  Returns:
    (bytes): The packet to send
  """
  length = _HEADER_SIZE   # Header is 14 bytes
  if message: length += len(message)   # Add the length of the message if it exists

  #             source port         destination port    length of message    checksum          seq #             id               number of packets
  dummyHeader = sPort.to_bytes(2) + dPort.to_bytes(2) + length.to_bytes(2) + (0).to_bytes(2) + seq.to_bytes(2) + id.to_bytes(2) + numPackets.to_bytes(2)    # Create dummy header
  dummyPacket = dummyHeader
  if message: dummyPacket += message    # Create dummy packet

  checksum = _calculateChecksum(dummyPacket)   # Calculate checksum

  #        source port         destination port    length of message    checksum               seq #             id               number of packets
  header = sPort.to_bytes(2) + dPort.to_bytes(2) + length.to_bytes(2) + checksum.to_bytes(2) + seq.to_bytes(2) + id.to_bytes(2) + numPackets.to_bytes(2)    # Create real header
  packet = header
  if message: packet += message   # Create real packet

  return packet   # Return packet


# ============================================================================================================
# Helper functions for rdt send
# ============================================================================================================


def _chunkMessage(message):
  """
  Chunks the message into a specific byte size

  Args:
    message (bytes): The full message to chunk

  Return:
    (list): A list of the chunks
  """
  chunks = []   # List for the chunks

  for i in range(0, len(message), _CHUNK_SIZE):   # For each chunk
    chunks.append(message[i : i + _CHUNK_SIZE])    # Append the chunk to the chunk list

  return chunks


# ============================================================================================================
# Helper functions for rdt receive
# ============================================================================================================


def _allPacketsReceived(numPackets, bufferedPackets):
  """
  Check if all packets have been received

  Args:
    numPackets (int): The number of packets to expect from the sender
    bufferedPackets (list): A list of seq numbers of the packets that have been received (can be out of order)

  Return:
    (bool): True if all the packets exist
  """
  for seqExpected in range(numPackets):
    if seqExpected not in bufferedPackets: return False   # If the seq number doesn't exist in the list of buffered packets, return false
  
  return True   # Return true if all the expected sequence numbers are in the buffered packets


def _processPackets(bufferedPackets, bufferedChunks, numPackets):
  """
  Process the contents of the packets

  Args:
    bufferedPackets (list): A list of sequence numbers in the order they arrived (may be out of order)
    bufferedChunks (list): A list of chunks in the order they arrived (same order as bufferedPackets)
    numPackets (int): The total number of packets

  Return:
    (str): A string for the return packet
  """
  message = None    # Message

  for seq in range(numPackets):   # For each packet sequence
    index = bufferedPackets.index(seq)    # Get the index of the sequence number
    if message is None: message = bufferedChunks[index]   # If the message is none (first packet), set the message to the chunk
    else: message += bufferedChunks[index]    # If the message already exists, add the chunk to the message
  
  return message    # Return the message


# ============================================================================================================
# RDT Send
# ============================================================================================================


def rdtSend(sPort, dPort, id, message, printDebug=False):
  """
  Sends the packets over rdt

  Args:
    sPort (int): The source port
    dPort (int): The destination port
    id (int): The ID of the message
    message (str): The message to send
    printDebug (bool): If this should print debug messages
  """
  global debugMode    # Get the global variable debugMode
  debugMode = printDebug    # Set the global variable to the printDebug parameter

  sock = None   # Socket

  try:    # Try to set the socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((_IP, sPort))
    sock.setblocking(False)   # Socket doesn't block the program
  except OSError as e:
    print(e)
    raise e

  message = message.encode('utf-8')
  numPackets = math.ceil(len(message) / _CHUNK_SIZE)    # Determine the total number of chunks to send
  messages = _chunkMessage(message)   # Chunk the message
  cwndStart = 0   # The start of the congestion window
  packetsInAir = []   # Which packets are in the air (sent but not acked)
  seq = 0   # Which packet we're on
  nextSeq = 0   # Which one will be sent next
  prevAck = -1    # The previous ack
  dupAcks = 0   # The number of duplicate acks
  timeoutStart = time.time()    # Start the timeout timer

  while prevAck < numPackets - 1:
    if len(packetsInAir) <= _CWND_SIZE and nextSeq < numPackets:   # Make sure there aren't too many packets in the air
      seq = nextSeq
      _printT(f'Sending packet {seq}')
      packet = _createPacket(sPort, dPort, seq, id, numPackets, messages[seq])    # Create a packet
      
      sock.sendto(packet, (_IP, _INTERMEDIARY_PORT))    # Send the packet to the intermediary

      packetsInAir.append(seq)    # Add the packet to the packets in air

      nextSeq += 1

    try:    # Try to receive data
      datagram, _ = sock.recvfrom(2048)   # Receive data

      if not _isValidDatagram(dPort, id, datagram):   # If it's an invalid datagram
        raise Exception('Invalid packet received')
      
      ack = int.from_bytes(datagram[8:10])    # Get the ack number

      if prevAck == ack:    # If it's the same as the last ack
        dupAcks += 1    # Increment dupAcks
        _printT(f'{dupAcks} duplicate ACK(s) {ack} received')
        if dupAcks >= 3:    # If the number of duplicate acks is >= 3
          if prevAck == 0: seq = 0
          else: seq = prevAck + 1   # Set the seq number to the first unacked packet
          _printT(f'Fast recovery initiated for packet {seq}')
          nextSeq = seq
          timeoutStart = time.time()    # Restart the timeout
          dupAcks = 0   # Reset the duplicate acks
          packetsInAir = []
      elif ack > prevAck:   # If ack is greater than last ack
        _printT(f'Received ACK {ack}')
        timeoutStart = time.time()    # Restart the timeout
        prevAck = ack   # Set prev ack to this ack
        dupAcks = 0     # Reset number of duplicate acks

      if ack >= cwndStart:    # If the ack is greater than the start of the congestion window
        cwndStart = ack + 1   # Set the cwnd to the next unacked packet
        for packetSeq in packetsInAir:    # For each packet in the packets in air
          if packetSeq <= ack: packetsInAir.remove(packetSeq)   # If the seq <= ack, it has been received, so remove from packets in air
        timeoutStart = time.time()    # Reset the timeout
      
      if ack > seq:   # If the ack is greater than the seq number, set seq to first unacked packet
        seq = ack + 1
        nextSeq = seq
    except Exception: pass   # No data was ready, so we ignore it

    # If a timeout occurs
    if time.time() - timeoutStart > _TIMEOUT: 
      _printT(f'Timeout with CWND at {cwndStart}')
      timeoutStart = time.time()    # Reset everything
      seq = cwndStart
      nextSeq = cwndStart
      packetsInAir = []

  _printT('Packet Sent!')

  sock.close()


# ============================================================================================================
# RDT Receive
# ============================================================================================================


def rdtReceive(id, dPort, sPort=None, timeout=-1, printDebug=False):
  """
  Receive and handle the packets that come into the client

  Args:
    id (int): The ID of the message
    dPort (int): The port of the receiver
    sPort (int): The port of the sender
    timeout (int): How many seconds this function should try to receive a message before returning None
    printDebug (bool): If this should print debug messages

  Returns:
    (int): The port number of the sender
    (str): The message
  """
  global debugMode    # Get the global var
  debugMode = printDebug    # Set whether the function should print debug messages

  sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)   # Create the socket
  sock.bind((_IP, dPort))
  sock.setblocking(False)

  cwndStart = 0   # Set all variables to default values
  bufferedPackets = []
  bufferedChunks = []
  numPackets = None
  resetTimer = None
  fullMessage = None
  timeoutStart = time.time()

  while True:   # While true
    try:    # Try to receive data
      datagram, _ = sock.recvfrom(2048)   # Get the packet. If no packet exists, throws an error

      if not _isValidDatagram(sPort, id, datagram):   # If the datagram is valid
        raise Exception('Invalid packet received')
      
      timeoutStart = None   # If we get a valid packet, we stop the timeout timer
        
      if resetTimer is not None: resetTimer = time.time()   # If the timer is already running and we get another packet, reset it

      if sPort is None: sPort = int.from_bytes(datagram[_SPORT_HDR_LOC:_DPORT_HDR_LOC])   # If we're not listening to a specific socket, set the sPort to the first message
      if numPackets is None: numPackets = int.from_bytes(datagram[_NUM_PKT_HDR_LOC:_MSG_HDR_LOC])   # If we don't know how many packets there are in total, set it
      seqReceived = int.from_bytes(datagram[_SEQ_HDR_LOC:_ID_HDR_LOC])    # Get the sequence number
      chunkReceived = datagram[_MSG_HDR_LOC:].decode('utf-8')   # Get the chunk

      _printT(f'Received packet {seqReceived} from client')

      if seqReceived not in bufferedPackets:    # If the sequence number is not in the buffered packets
        bufferedPackets.append(seqReceived)   # Add it to the buffered packets 
        bufferedChunks.append(chunkReceived)    # Also add the chunk to the buffered chunks

      if fullMessage is None and _allPacketsReceived(numPackets, bufferedPackets):    # If all the packets have been received and the message hasn't been set
        fullMessage = _processPackets(bufferedPackets, bufferedChunks, numPackets)   # Process the messages from the packets
        resetTimer = time.time()    # Start the reset timer (There needs to be a timer in case the final ACK is lost and the client retransmits)

      if seqReceived == cwndStart:    # If the sequence is the start of the cwnd
        seq = cwndStart   # Set the seq
        while True:
          if seq in bufferedPackets: seq += 1   # Increase the sequence number if it exists in buffered packets
          else:   # If it doesn't exist
            cwndStart = seq   # Set cwnd to seq (If we're waiting on packet 3, and packets 4, 5, and 6 are buffered, this will set the cwnd to 7 once packet 3 is received)
            break

      packet = _createPacket(dPort, sPort, max(0, cwndStart - 1), id, numPackets, None)   # Create a packet
      _printT(f'Sending ack {max(0, cwndStart - 1)}')

      sock.sendto(packet, (_IP, _INTERMEDIARY_PORT))    # Send the packet
      
    except Exception: pass   # No data was ready, so we move on it

    if resetTimer and time.time() - resetTimer > _RESET_TIME:    # If the reset timer has been started and it's past the limit
      sock.close()    # Close the socket
      _printT('Packet Received!')
      
      return sPort, fullMessage
    
    if timeout >= 0 and timeoutStart is not None and time.time() - timeoutStart > timeout: return None, None    # If the timeout exists and has been reached, return None
