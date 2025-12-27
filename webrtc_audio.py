#!/usr/bin/env python3
import asyncio, json, gi, logging

gi.require_version("Gst", "1.0")
gi.require_version("GstWebRTC", "1.0")
from gi.repository import Gst, GstWebRTC
import websockets

logging.basicConfig(level=logging.INFO)
Gst.init(None)

PIPELINE = """
audiotestsrc is-live=true !
audioconvert !
audioresample !
opusenc !
rtpopuspay pt=96 !
queue name=rtp_queue
"""

pipeline = Gst.parse_launch(PIPELINE)

webrtc = Gst.ElementFactory.make("webrtcbin", "webrtc")
webrtc.set_property("bundle-policy", "max-bundle")
pipeline.add(webrtc)

queue = pipeline.get_by_name("rtp_queue")
srcpad = queue.get_static_pad("src")

# 🔥 pad が出てきた瞬間に link する
def on_pad_added(element, pad):
    logging.info("webrtcbin pad added: %s", pad.get_name())
    if pad.get_direction() != Gst.PadDirection.SINK:
        return
    if srcpad.is_linked():
        return
    ret = srcpad.link(pad)
    assert ret == Gst.PadLinkReturn.OK, "pad link failed"
    logging.info("RTP linked to webrtcbin")

webrtc.connect("pad-added", on_pad_added)

# transceiver は negotiation 用に必要
webrtc.emit(
    "add-transceiver",
    GstWebRTC.WebRTCRTPTransceiverDirection.SENDONLY,
    Gst.Caps.from_string(
        "application/x-rtp,media=audio,encoding-name=OPUS,clock-rate=48000,payload=96"
    )
)

# ---------- WebRTC signaling ----------
clients = set()
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

def on_negotiation_needed(element):
    logging.info("Negotiation needed")
    promise = Gst.Promise.new_with_change_func(on_offer_created, element, None)
    element.emit("create-offer", None, promise)

def on_offer_created(promise, element, _):
    promise.wait()
    offer = promise.get_reply().get_value("offer")
    element.emit("set-local-description", offer, None)
    msg = {"type": "offer", "sdp": offer.sdp.as_text()}
    for ws in clients:
        asyncio.run_coroutine_threadsafe(ws.send(json.dumps(msg)), loop)

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
        if data.get("type") == "answer":
            sdp = Gst.SDPMessage.new()
            Gst.SDPMessage.parse_buffer(data["sdp"].encode(), sdp)
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
    clients.remove(ws)

async def main():
    pipeline.set_state(Gst.State.PLAYING)
    logging.info("Pipeline PLAYING")
    async with websockets.serve(ws_handler, "0.0.0.0", 9001):
        await asyncio.Future()

loop.run_until_complete(main())
