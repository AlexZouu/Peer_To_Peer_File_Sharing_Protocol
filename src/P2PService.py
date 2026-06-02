import base64
import json
import math
from pathlib import Path
import threading
from RDT.ReliableDataTransfer import rdtSend, rdtReceive
from API.PeerAPI import GET_chunk, GET_fileLen
from API.TrackerAPI import PUT_file


TRACKER_PORT = 1025          # Port of the tracking program


def requestChunk(lock, tempPort, dPort, filename, chunkSize, fileLen, index, messages):
  """
  The function responsible for actually requesting a chunk

  Args:
    lock (Lock): The lock to lock the dictionary that stores the chunk received
    tempPort (int): The port to send the request on
    dPort (int): The port of the peer to request the chunk from
    filename (str): The name of the file to request
    chunkSize (int): The size of the chunk to request
    index (int): The index of this thread
    messages (dict): The dictionary to put the chunk in
  """
  startByte = chunkSize * index   # Calculate the start byte

  if startByte > fileLen - 1: return

  # Request the chunk from the peer
  chunk = GET_chunk(tempPort, dPort, filename, startByte, chunkSize)    # Get the chunk

  with lock: messages[index] = chunk    # Using the lock, put the chunk into the dictionary


def requestFile(availablePorts, peers, filename, nickname):
  """
  The function that handles requesting files from other peers

  Args:
    availablePorts (Queue): A queue of all the available ports for parallelism
    peers (list): List of peers that have the file
    filename (str): The name of the file the user wishes to download
    nickname (str): The nickname of the user
  """
  getFileLengthPort = availablePorts.get()    # Get a port to request the length of the file

  fileLen = GET_fileLen(getFileLengthPort, peers[0], filename)    # Receive the file length

  availablePorts.put(getFileLengthPort)   # Release the port used to get the legnth back 

  chunkSize = math.ceil(fileLen / len(peers))   # Calculate the chunk size

  threads = []    # List of threads
  portsInUse = []   # List of ports in use
  lock = threading.Lock()   # The lock used to lock the dictionary storing the received chunks
  messages = {}   # The dictionary containing the chunks received from the other users

  for index, dPort in enumerate(peers):   # For each peer
    makeRequestPort = availablePorts.get()    # Get a port to make the request
    portsInUse.append(makeRequestPort)    # Add the port to the list of ports in use
    # Create the thread to actually request the chunk
    chunkRequestThread = threading.Thread(target=requestChunk, args=[lock, makeRequestPort, dPort, filename, chunkSize, fileLen, index, messages])
    threads.append(chunkRequestThread)    # Add the thread to the list of threads
    chunkRequestThread.start()    # Start the thread

  for thread in threads: thread.join()    # Wait for each thread to return

  for port in portsInUse: availablePorts.put(port)    # Release all the ports that were used

  with open(f'Users\\{nickname}\\{filename}', 'wb') as f:    # Open the file to write the chunks
    for key in range(len(messages)): f.write(messages[key])   # Write the chunks in order to the file

  informTrackerPort = availablePorts.get()    # Get another port to inform the tracker of the new file

  PUT_file(informTrackerPort, filename, nickname)   # Inform the tracker of the new file

  availablePorts.put(informTrackerPort)   # Release the port


def handleRequest(availablePorts, sPort, message, path):
  """
  The main function to handle requests from other users

  Args:
    availablePorts (Queue): A queue of all the available ports for parallelism
    sPort (int): The port of the user who sent the request
    messages (dict): The dictionary from the requester
    path (str): The path to the user's files
  """
  tempPort = availablePorts.get()   # Get a temporary port

  if message.get('request') == 'GET_fileLen':    # If the requester is looking for the length of a file
    filename = message.get('filename')    # Get the name of the file

    packet = {
      'status': 'OK',
      'fileLength': Path(path + filename).stat().st_size    # Get the size of the file
    }

    rdtSend(tempPort, sPort, 0, json.dumps(packet))   # Send the file length to the requester
  elif message.get('request') == 'GET_chunk':    # If the requester is requesting a chunk
    filename = message.get('filename')    # Get the filename
    startByte = message.get('chunkStart')    # Get the start byte of the chunk
    chunkSize = message.get('chunkSize')    # Get the end byte of the chunk

    chunk = None

    with open(path + filename, 'rb') as f: 
      f.seek(startByte)    # Go to the start byte
      chunk = f.read(chunkSize)    # Read the file in bytes

    packet = {
      'status': 'OK',
      'chunk': base64.b64encode(chunk).decode('utf-8')   # Get the chunk
    }

    rdtSend(tempPort, sPort, 0, json.dumps(packet))    # Send the chunk to the requester

  availablePorts.put(tempPort)    # Add the temp port back to the queue of additional ports