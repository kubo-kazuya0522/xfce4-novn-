#!/usr/bin/env python3
import asyncio
import json
import gi
import logging

gi.require_version("Gst", "1.0")
gi.require_version("GstWebRTC", "1.0")
from gi.repository import Gst, GstWebRTC

import websockets

# --------------------------------------------------
# basic setup
# --------------------------------------------------
logging.basicConfig(level=logging.INFO)
Gst.init(None)

# --------------------------------------------------
# RTP pipeline (audio → RTP OPUS)
# --------------------------------------------------
PIPELINE = """
audiotestsrc is-live=true !
audioconvert !
audioresample !
opusenc !
rtpopuspay pt=96 !
application/x-rtp,media=audio,encoding-name=OPUS,clock-rate=48000,payload=96 !
queue name=rtp_queue
"""

pipeline = Gst.parse_launch(PIPELINE)
queue = pipeline.get_by_name("rtp_queue")

# --------------------------------------------------
# webrtcbin
# --------------------------------------------------
webrtc = Gst.ElementFactory.make("webrtcbin", "webrtc")
webrtc.set_property("bundle-policy", "max-bundle")
pipeline.add(webrtc)

# transceiver を先に作る（必須）
webrtc.emit(
    "add-transceiver",
    GstWebRTC.WebRTCRTPTransceiverDirection.SENDONLY,
    Gst.Caps.from_string(
        "application/x-rtp,media=audio,encoding-name=OPUS,clock-rate=48000,payload=96"
    )
)

# --------------------------------------------------
# ★ 核心：pad-added で RTP を link
# --------------------------------------------------
def on_webrtc_pad_added(element, pad):
    logging.info(f"webrtcbin pad-added: {pad.get_name()}")

    srcpad = queue.get_static_pad("src")
    if srcpad.is_linked():
        return

    ret = srcpad.link(pad)
    if ret == Gst.PadLinkReturn.OK:
        logging.info("RTP linked to webrtcbin")
    else:
        logging.error(f"Link failed: {ret}")

webrtc.connect("pad-added", on_webrtc_pad_added)

# --------------------------------------------------
# WebRTC signaling
# --------------------------------------------------
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

    msg = {
        "type": "offer",
        "sdp": offer.sdp.as_text()
    }

    for ws in clients:
        asyncio.run_coroutine_threadsafe(
            ws.send(json.dumps(msg)), loop
        )

def on_ice_candidate(element, mline, candidate):
    msg = {
        "ice": {
            "candidate": candidate,
            "sdpMLineIndex": mline
        }
    }
    for ws in clients:
        asyncio.run_coroutine_threadsafe(
            ws.send(json.dumps(msg)), loop
        )

webrtc.connect("on-negotiation-needed", on_negotiation_needed)
webrtc.connect("on-ice-candidate", on_ice_candidate)

# --------------------------------------------------
# WebSocket server
# --------------------------------------------------
async def ws_handler(ws):
    clients.add(ws)
    try:
        async for msg in ws:
            data = json.loads(msg)

            if data.get("type") == "answer":
                sdp = Gst.SDPMessage.new()
                Gst.SDPMessage.parse_buffer(
                    data["sdp"].encode(), sdp
                )
                answer = GstWebRTC.WebRTCSessionDescription.new(
                    GstWebRTC.WebRTCSDPType.ANSWER, sdp
                )
                webrtc.emit("set-remote-description", answer, None)

            elif "ice" in data:
                webrtc.emit(
                    "add-ice-candidate",
                    data["ice"]["sdpMLineIndex"],
                    data["ice"]["candidate"]
                )
    finally:
        clients.remove(ws)

# --------------------------------------------------
# main
# --------------------------------------------------
async def main():
    pipeline.set_state(Gst.State.PLAYING)
    logging.info("Pipeline PLAYING")

    async with websockets.serve(ws_handler, "0.0.0.0", 9001):
        logging.info("WebSocket signaling on :9001")
        await asyncio.Future()  # forever

if __name__ == "__main__":
    loop.run_until_complete(main())
