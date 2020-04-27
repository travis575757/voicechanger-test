#!/usr/bin/env python

# WS server example that synchronizes state across clients

import asyncio
import json
import logging
import websockets
import base64
import time
import threading
import numpy as np
from random import randint
import uuid
from effects import *

buffer_size = 2048 // 2     # size of audio buffers passed to server
sf = 44100                  # sampled rate assumed for clients

class User:

    def __init__(self,websocket):
        self.websocket = websocket      #users websocket connection
        self.mute_self = True           #disables test microphone feature
        self.name = ""                  #username
        self.id = str(uuid.uuid1())     #unique id of the user

        # config defaults
        self.config = {                 #dict of configuration used by user effects
            "volume": 1,
            "fs": sf,
            "distortion_amp": 1,
            "distortion_cutoff": 1,
            "robot_decimation": 1,
            "pitch_shift": 1,

            "distortion_enable": 0,
            "robot_enable": 0,
            "robot_reduce":0,
            "pitch_enable":0,
            "bassboost_enable":0,
            "bassboost_amp":1,
        }

        self.effects = [                                #list of effects accessible to the user
            VolumeEffect(buffer_size,self.config),
            DistortionEffect(buffer_size,self.config),
            RobotEffect(buffer_size,self.config),
            PitchEffect(buffer_size,self.config),
            BassBoostEffect(buffer_size,self.config)
        ]

    def process(self,data):                             #process audio sample for the user, data is passed sequentially through each effect
        data = np.array(data)
        for effect in self.effects:
            data = effect.process(data)
        return data.tolist()
        
logging.basicConfig()

USERS = set()           #list of users connected

# event messages sent to the client from the server, either audio event or user state change event

def users_event():
    return json.dumps({"type": "users", "count": len(USERS), "users": [user.name for user in USERS]})

def audio_event(samples,time,owner):
    return json.dumps({"type": "audio", "sample": owner.process(samples), "time": int(time), "owner": owner.id})

# events to either notify user of audio event (audio being sent to the client) or usage state change event (user connected,disconnected,changed username)

async def notify_users():
    if USERS:
        message = users_event()
        await asyncio.wait([user.websocket.send(message) for user in USERS])

async def notify_audio(sender,samples,t):
    message = audio_event(samples,t,sender)
    coroutines = [ user.websocket.send(message) for user in USERS if sender is not user or not user.mute_self ]
    if coroutines:
        await asyncio.wait(coroutines)
    print("recv delay: {}".format( 1000 * time.time() - t ), end="\r")


# register / unregister user events to remove from local user listing

async def register(user):
    USERS.add(user)
    await notify_users()

async def unregister(user):
    USERS.remove(user)
    await notify_users()

# main user connection instance

async def client_session(websocket, path):
    user = User(websocket)
    await register(user)
    try:
        # process each message recieved by the user
        async for message in websocket:
            data = json.loads(message)
            if data["action"] == "audio":       # audio samples are being sent from the user
                # ignore invalid buffer sizes
                if ( len(data["audio"]) == buffer_size ):
                    await notify_audio( user, data["audio"], data["time"] )
            elif data["action"] == "config":    # the user is changing a effect config
                user.config[ data["type"] ] = float(data["value"])
            elif data["action"] == "mute_self": # the user is enabling or disabling test microphone
                user.mute_self = data["value"]
            elif data["action"] == "setname":   # the user is setting their username
                user.name = data["value"]
                await notify_users()
            else:
                logging.error("unsupported event: {}", data)
    finally:
        await unregister(user)

start_server = websockets.serve(client_session, "0.0.0.0", 6789)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
