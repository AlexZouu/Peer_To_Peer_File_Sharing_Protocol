import json
import math
from RDT.ReliableDataTransfer import rdtSend, rdtReceive


IP = '127.0.0.1'              # IP address of the server (same machine)
TRACKER_PORT = 49999          # Port of the tracking program


def sendResponse(peerPort, packet):
  rdtSend(TRACKER_PORT, peerPort, 0, json.dumps(packet))


def initiatePeer(peerTable, peerPort, message):
  """
  Handle a new peer joining the system

  Args:
    peerTable (dict): A dictionary containing all the peers and the files they have
    peerPort (int): The port of the new peer
    message (dict): A dict of the incoming request
  """
  packet = {}

  if peerTable.get(peerPort) is not None:
    packet['status'] = 'ERROR'
    packet['errMsg'] = 'The specified port is already in use, please choose another'
    sendResponse(peerPort, packet)
    return
  
  filesInPossession = message.get('files')

  if len(filesInPossession) > 0: peerTable[peerPort] = filesInPossession    # If the peer has files, add it to the table
  else: peerTable[peerPort] = None    # Otherwise, note that the peer has no files

  packet = {
    'status': 'OK'
  }

  sendResponse(peerPort, packet)    # Send a response informing the peer everythings set up

  print(f'Peer {peerPort} has joined!')


def getPeersWithFile(peerTable, peerPort, message):
  """
  Return a list of peers with a specific file

  Args:
    peerTable (dict): A dictionary containing all the peers and the files they have
    peerPort (int): The port requesting the list of peers
    message (dict): A dict of the incoming request
  """
  filename = message.get('filename')

  if (filename is None):
    packet = {
      'status': 'ERROR',
      'message': 'The name of the file must be included in the message'
    }

    sendResponse(peerPort, packet)
    return
  
  peerList = []

  for port, files in peerTable.items():     # For each peers files
    if files is not None and port != peerPort and filename in files: peerList.append(port)    # If the file exists and it's not the requester, add the peer to the list

  packet = {}

  if len(peerList) == 0:
    packet['status'] = 'ERROR'
    packet['errMsg'] = 'No files are available currently'   # If no peer has the file, send an error
    sendResponse(peerPort, packet)
    print(f'Peer {peerPort} requested a list of peers with {filename} but it doesn\'t exist!')
  else:
    packet['status'] = 'OK'
    packet['peers'] = peerList
    sendResponse(peerPort, packet)    # Otherwise, send the list of peers with the file
    print(f'Peer {peerPort} requested a list of peers with {filename}!')



def getAvailableFiles(peerTable, peerPort):
  """
  Return a list of available files

  Args:
    peerTable (dict): A dictionary containing all the peers and the files they have
    peerPort (int): The port of the peer requesting the list of files
  """
  fileList = []

  for port, files in peerTable.items():   # For each port and their files
    if port == peerPort: continue   # If it's the requesting port, skip it
    if files is None: continue    # If the port has no files, skip it

    for filename in files:    # For each file
      if filename not in fileList and filename not in peerTable[peerPort]: fileList.append(filename)    # If the file isn't already in the list, add it

  packet = {}

  if len(fileList) == 0:
    packet['status'] = 'ERROR'
    packet['errMsg'] = 'No files are available currently'   # If no files are available, send an error
    sendResponse(peerPort, packet)
  else:
    packet['status'] = 'OK'
    packet['files'] = fileList
    sendResponse(peerPort, packet)    # Otherwise, return the list of files

  print(f'Peer {peerPort} has asked for all available files!')


def addToPeerTable(peerTable, peerPort, message):
  """
  Add a file to the peer table

  Args:
    peerTable (dict): A dictionary containing all the peers and the files they have
    peerPort (int): The port of the peer adding a file
    message (dict): A dict of the incoming request
  """
  actualPort = math.floor(peerPort / 100) * 100   # The request to add a file can come from one of the additional ports, so we need to get the actual port

  filename = message.get('filename')

  if (filename is None):
    packet = {
      'status': 'ERROR',
      'message': 'The name of the file must be included in the message'
    }

    sendResponse(peerPort, packet)
    return

  fileList = peerTable[actualPort]    # Get the file list of the peer
  if fileList is not None and filename not in fileList: fileList.append(filename)   # If the file list exists, add the filename
  else: fileList = [filename]   # If it doesn't exist, set it to a list containing the file

  packet = { 'status': 'OK' }
  sendResponse(peerPort, packet)    # Otherwise, return the list of files

  print(f'Peer {actualPort} has aquired {filename}!')


def deleteFromPeerTable(peerTable, peerPort, message):
  """
  Delete a file from the peer table

  Args:
    peerTable (dict): A dictionary containing all the peers and the files they have
    peerPort (int): The port of the user that's deleting a file
    message (dict): A dict of the incoming request
  """
  filename = message.get('filename')

  if (filename is None):
    packet = {
      'status': 'ERROR',
      'message': 'The name of the file must be included in the message'
    }
    
    sendResponse(peerPort, packet)
    return
  
  if peerTable[peerPort] is None or filename not in peerTable[peerPort]: 
    packet = { 'status': 'OK' }
    sendResponse(peerPort, packet)    # If the file doesn't exist, just return
    print(f'Peer {peerPort} tried to delete {filename}, but it\'s already gone (and that\'s ok)!')
    return
  
  peerTable[peerPort].remove(filename)    # Otherwise, remove the file

  packet = { 'status': 'OK' }
  sendResponse(peerPort, packet)    # Otherwise, return the list of files

  print(f'Peer {peerPort} has deleted {filename}!')


def closePeerConnection(peerTable, peerPort):
  """
  Disconnect a peer from the system

  Args:
    peerTable (dict): A dictionary containing all the peers and the files they have
    peerPort (int): The peer leaving the system
  """
  peerTable.pop(peerPort)   # Remove the peer from the table

  packet = { 'status': 'OK' }
  sendResponse(peerPort, packet)    # Otherwise, return the list of files

  print(f'Peer {peerPort} has left!')


def tracker():
  """
  The main tracker function
  """
  peerTable = {}    # Dictionary of peers and the files they have

  while True:
    peerPort, message = rdtReceive(0, TRACKER_PORT)   # Wait for a request

    messageDict = json.loads(message)

    match messageDict.get('request'):    # Determine the request and call the correct function
      case 'POST_user': initiatePeer(peerTable, peerPort, messageDict)
      case 'GET_usersWithFile': getPeersWithFile(peerTable, peerPort, messageDict)
      case 'PUT_file': addToPeerTable(peerTable, peerPort, messageDict)
      case 'DELETE_file': deleteFromPeerTable(peerTable, peerPort, messageDict)
      case 'GET_availableFiles': getAvailableFiles(peerTable, peerPort)
      case 'DELETE_user': closePeerConnection(peerTable, peerPort)


def main():
  """
  The main entry point to the program
  """
  tracker()


main()