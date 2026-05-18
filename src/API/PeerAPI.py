import sys
sys.path.append('../')

import base64
import json
from RDT.ReliableDataTransfer import rdtSend, rdtReceive


TRACKER_PORT = 49999          # Port of the tracking program


def sendPacket(sPort, dPort, packet):
  """
  The function that handles actually sending the request

  Args:
    sPort (int): The main port number the user is assigned to
    dPort (int): The main port number of the receiving peer
    packet (dict): The packet being sent to the tracker

  Return:
    (int): The port of the receiver
    (dict): The message returned by the receiver
  """
  rdtSend(sPort, dPort, 0, json.dumps(packet))   # Send a request to the tracker to get the available files
  receiverPort, message = rdtReceive(0, sPort)    # Receive the files

  messageDict = json.loads(message)

  if messageDict.get('status') != 'OK':
    raise Exception(messageDict.get('errMsg'))

  return receiverPort, messageDict


def GET_fileLen(sPort, dPort, filename):
  """
  Gets the length of a file

  Args:
    sPort (int): The port of the peer sending the request
    dPort (int): The port of the peer to request the chunk from
    filename (str): The name of the file

  Return:
    (int): The size of the file in bytes
  """
  packet = {
    'request': 'GET_fileLen',
    'filename': filename
  }

  _, message = sendPacket(sPort, dPort, packet)

  return message.get('fileLength')


def GET_chunk(sPort, dPort, filename, chunkStart, chunkSize):
  """
  The function responsible for actually requesting a chunk

  Args:
    sPort (int): The port of the peer sending the request
    dPort (int): The port of the peer to request the chunk from
    filename (str): The name of the file
    chunkStart (int): The start byte of the chunk
    chunkSize (int): The size of the chunk in bytes

  Return:
    (bytes): The chunk of the file in bytes
  """
  packet = {
    'request': 'GET_chunk',
    'filename': filename,
    'chunkStart': chunkStart,
    'chunkSize': chunkSize
  }

  # Request the chunk from the peer
  _, message = sendPacket(sPort, dPort, packet)

  return base64.b64decode(message.get('chunk').encode('utf-8'))