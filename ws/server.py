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

buffer_size = 2048 // 2
sf = 44100

class User:

    def __init__(self,websocket):
        self.websocket = websocket
        self.mute_self = True
        self.name = ""
        self.id = str(uuid.uuid1())

        # config defaults
        self.config = {
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
            "delay_enable":0,
            "delay_amount":0
        }

        self.effects = [
            VolumeEffect(buffer_size,self.config),
            DistortionEffect(buffer_size,self.config),
            RobotEffect(buffer_size,self.config),
            PitchEffect(buffer_size,self.config),
            BassBoostEffect(buffer_size,self.config),
            DelayEffect(buffer_size,self.config)
        ]

    def process(self,data):
        data = np.array(data)
        for effect in self.effects:
            data = effect.process(data)
        return data.tolist()
        
logging.basicConfig()

USERS = set()

def users_event():
    return json.dumps({"type": "users", "count": len(USERS), "users": [user.name for user in USERS]})

def audio_event(samples,time,owner):
    return json.dumps({"type": "audio", "sample": owner.process(samples), "time": int(time), "owner": owner.id})

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

async def register(user):
    USERS.add(user)
    await notify_users()

async def unregister(user):
    USERS.remove(user)
    await notify_users()

async def client_session(websocket, path):
    user = User(websocket)
    await register(user)
    try:
        async for message in websocket:
            data = json.loads(message)
            if data["action"] == "audio":
                # ignore invalid buffer sizes
                if ( len(data["audio"]) == buffer_size ):
                    await notify_audio( user, data["audio"], data["time"] )
            elif data["action"] == "config":
                user.config[ data["type"] ] = float(data["value"])
            elif data["action"] == "mute_self":
                user.mute_self = data["value"]
            elif data["action"] == "setname":
                user.name = data["value"]
                await notify_users()
            else:
                logging.error("unsupported event: {}", data)
    finally:
        await unregister(user)

start_server = websockets.serve(client_session, "0.0.0.0", 6789)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
