@kubo-kazuya0522 ➜ ~/デスクトップ $ gst-launch-1.0 -v \
>   pulsesrc device=webrtc.monitor ! \
>   audioconvert ! audioresample ! \
>   opusenc ! rtpopuspay ! \
>   webrtcbin name=webrtc stun-server=stun://stun.l.google.com:19302
WARNING: erroneous pipeline: rtpopuspay0 を webrtc へリンクできません