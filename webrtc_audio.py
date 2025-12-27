#!/usr/bin/env python3
import asyncio
import json
import logging
import gi

gi.require_version("Gst", "1.0")
gi.require_version("GstWebRTC", "1.0")
from gi.repository import Gst, GstWebRTC, GLib

import websockets

logging.basicConfig(level=logging.INFO)
Gst.init(None)

# ----- GStreamer pipeline -----
pipeline = Gst.Pipeline.new("audio-pipeline")

# audiotestsrc
src = Gst.ElementFactory.make("audiotestsrc", "src")
src.set_property("is-live", True)

# convert/resample/encode
conv = Gst.ElementFactory.make("audioconvert", "conv")
resample = Gst.ElementFactory.make("audioresample", "resample")
enc = Gst.ElementFactory.make("opusenc", "enc")
pay = Gst.ElementFactory.make("rtpopuspay", "pay")
pay.set_property("pt", 96)

# webrtcbin
webrtc = Gst.ElementFactory.make("webrtcbin", "webrtc")
webrtc.set_property("bundle-policy", "max-bundle")

for e in [src, conv, resample, enc, pay, webrtc]:
    pipeline.add(e)

src.link(conv)
conv.link(resample)
resample.link(enc)
enc.link(pay)
pay.link(webrtc)

clients = set()
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# ----- Offer 作成 -----
def on_offer_created(promise, element, _):
    promise.wait()
    offer = promise.get_reply().get_value("offer")
    if not offer:
        logging.error("Offer is None")
        return
    element.emit("set-local-description", offer, None)
    msg = {"type": "offer", "sdp": offer.sdp.as_text()}
    for ws in clients:
        asyncio.run_coroutine_threadsafe(ws.send(json.dumps(msg)), loop)
    logging.info("Offer sent to clients")

# ----- ICE candidate -----
def on_ice_candidate(element, mline, candidate):
    msg = {"ice": {"candidate": candidate, "sdpMLineIndex": mline}}
    for ws in clients:
        asyncio.run_coroutine_threadsafe(ws.send(json.dumps(msg)), loop)

webrtc.connect("on-ice-candidate", on_ice_candidate)

# ----- Add transceiver and create offer immediately -----
webrtc.emit(
    "add-transceiver",
    GstWebRTC.WebRTCRTPTransceiverDirection.SENDONLY,
    Gst.Caps.from_string(
        "application/x-rtp,media=audio,encoding-name=OPUS,clock-rate=48000,payload=96"
    )
)

promise = Gst.Promise.new_with_change_func(on_offer_created, webrtc, None)
webrtc.emit("create-offer", None, promise)

# ----- WebSocket handler -----
async def ws_handler(ws):
    clients.add(ws)
    try:
        async for msg in ws:
            try:
                data = json.loads(msg)
                if data.get("type") == "answer":
                    from gi.repository import GstSDP
                    sdp = Gst.SDPMessage.new()
                    Gst.SDPMessage.parse_buffer(data["sdp"].encode(), sdp)
                    answer = GstWebRTC.WebRTCSessionDescription.new(
                        GstWebRTC.WebRTCSDPType.ANSWER, sdp
                    )
                    webrtc.emit("set-remote-description", answer, None)
                    logging.info("Remote description set from client answer")
                elif "ice" in data:
                    webrtc.emit(
                        "add-ice-candidate",
                        data["ice"]["sdpMLineIndex"],
                        data["ice"]["candidate"]
                    )
                    logging.info("Added ICE candidate from client")
            except Exception as e:
                logging.error("Error handling message: %s", e)
    except Exception as e:
        logging.error("WebSocket handler failed: %s", e)
    finally:
        clients.discard(ws)
        await ws.close()
        logging.info("WebSocket connection closed")

# ----- main loop -----
async def main():
    pipeline.set_state(Gst.State.PLAYING)
    logging.info("Pipeline PLAYING")
    async with websockets.serve(ws_handler, "0.0.0.0", 9001):
        logging.info("WebSocket server listening on 0.0.0.0:9001")
        await asyncio.Future()  # 永久待機

loop.run_until_complete(main())
