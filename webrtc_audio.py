#!/usr/bin/env python3
import asyncio
import json
import gi
import logging
gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib

import websockets

logging.basicConfig(level=logging.INFO)

Gst.init(None)

PIPELINE = """
audiotestsrc is-live=true !
audioconvert !
audioresample !
opusenc !
rtpopuspay !
application/x-rtp,media=audio,encoding-name=OPUS,clock-rate=48000,payload=96 !
webrtcbin name=webrtc
"""

# GStreamer パイプライン作成
pipeline = Gst.parse_launch(PIPELINE)
webrtc = pipeline.get_by_name("webrtc")

# WebSocket 接続を管理
clients = set()
loop = asyncio.get_event_loop()

def on_negotiation_needed(element):
    logging.info("Negotiation needed")
    promise = Gst.Promise.new_with_change_func(on_offer_created, element, None)
    element.emit("create-offer", None, promise)

def on_offer_created(promise, element, _):
    promise.wait()
    reply = promise.get_reply()
    offer = reply.get_value("offer")
    element.emit("set-local-description", offer, None)

    sdp = {"type": "offer", "sdp": offer.sdp.as_text()}
    for ws in clients:
        asyncio.run_coroutine_threadsafe(ws.send(json.dumps(sdp)), loop)

def on_ice_candidate(element, mline, candidate):
    msg = {"ice": {"candidate": candidate, "sdpMLineIndex": mline}}
    for ws in clients:
        asyncio.run_coroutine_threadsafe(ws.send(json.dumps(msg)), loop)

webrtc.connect("on-negotiation-needed", on_negotiation_needed)
webrtc.connect("on-ice-candidate", on_ice_candidate)

async def ws_handler(ws):
    clients.add(ws)
    async for msg in ws:
        data = json.loads(msg)
        if "sdp" in data:
            sdp = Gst.SDPMessage.new()
            Gst.SDPMessage.parse_buffer(data["sdp"].encode(), sdp)
            answer = Gst.WebRTCSessionDescription.new(Gst.WebRTCSDPType.ANSWER, sdp)
            webrtc.emit("set-remote-description", answer, None)
        elif "ice" in data:
            ice = data["ice"]
            webrtc.emit("add-ice-candidate", ice["sdpMLineIndex"], ice["candidate"])
    clients.remove(ws)

async def main():
    pipeline.set_state(Gst.State.PLAYING)
    async with websockets.serve(ws_handler, "0.0.0.0", 9001):
        await asyncio.Future()  # 永久待機

if __name__ == "__main__":
    loop.run_until_complete(main())
