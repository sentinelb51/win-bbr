# win-bbr
Properly using the BBRv2 TCP congestion control algorithm on Windows

# Overview
This repository documents the current issues with enabling BBRv2 on Windows and why they occur, as well as providing a workaround to preserve BBR performance while saving unsuspecting users a headache. If you're interested in technical details/explanations, skip ahead to the end of the write-up.

## Symptoms and observations
BBRv2 on Windows causes TCP FIN to be withheld on loopback connections when the payload is less than ~32 KB:
- **Localhost** connections may hang indefinitely without a timeout;
- **Steam** is especially susceptible to this issue and will not launch properly. 

# Quick start
Step-by-step guide on how to enable BRRv2 the right way.

### 1. Check what congestion provider is used
#### CMD
```ps1
netsh int tcp show supplemental
```
<details>
  <summary>Expected output</summary>
  <img width="508" height="289" alt="image" src="https://github.com/user-attachments/assets/dd0e375f-90d7-4656-bb32-b364fe272d35" />
</details>

### 2. Set congestion provider to BBR2
Available values are: `none`, `ctcp`, `dctcp`, `cubic`, `bbr2`, `default` 
#### CMD
```ps1
netsh int tcp set supplemental template=internet congestionprovider=bbr2
```

<details>
  <summary>Expected output</summary>
  <img width="835" height="46" alt="image" src="https://github.com/user-attachments/assets/27726d56-ceb6-4080-80dc-e233c6e6aa6e" />
</details>

### 3. Disable large loopback MTU
#### CMD
```ps1
netsh int ipv4 set gl loopbacklargemtu=disable
```

> If this is not a viable option, you can instead [set custom socket options](#option-2-specific), or [disable auto-tuning](#option-1-global).

<details>
  <summary>Expected output</summary>
  <img width="596" height="40" alt="image" src="https://github.com/user-attachments/assets/6fe78680-09bf-4be7-9309-a14faee7efae" />
</details>

### 4. Verify the bug is fixed
Download the bbr2_repro.py file; this requires Python installed on your system.

#### CMD
```ps1
python bbr2_repro.py
```

If the bug is fixed, you should see **"OK"** for the small payload; otherwise you will see "STALLED", "TIMEOUT" 

<details>
  <summary>Expected output</summary>
  <img width="628" height="289" alt="image" src="https://github.com/user-attachments/assets/73e7fccf-d4e6-4197-9f97-de096bcc07b0" />

</details>

# Technical write-up
An attempt to explain stuff in Layman's terms while preserving techical detail. 

### What is a congestion control algorithm
When you send data over a network, it is [split into small packages called "packets"](https://en.wikipedia.org/wiki/Packet_switching), which travel through a series of computers (routers) to reach a destination. The network is a shared resource between multiple computers, and network performance can thus be constrained by factors like bandwidth and latency. When this happens, intermediary routers can be overwhelmed, causing packet loss. Packet loss hurts network performance because data has to be re-transmitted again, wasting bandwidth and time. 

A congestion control algorithm is software typically within an operating system that decides how fast to send packets into the network. These algorithms calculate a "Bandwidth-Delay Product" (BDP) by multiplying bandwidth (bits/sec) by round-trip-time (rtt; seconds), which is the total volume of data that can exist in-flight. Ideally, the algorithm tries to match the BDP as closely as possible; sending less than BDP is underutilising the link; sending more than BDP is overutilising. 

### The challenge
Measuring BDP accurately is tricky; to measure true minimum RTT, the network pipe must be completely empty, yet to measure maximum bandwidth, the network pipe must be completely full. 

### What is BBR
BBR stands for "Bottleneck Bandwidth and RTT" and was developed by Google in 2016. Unlike other algorithms, it is not a loss-based algorithm, but rather builds an internal mathematical model of the network to estimate capacity. BBR periodically reduces the amount of data sent to drain queues and measure true physical latency (RTprop), as well as trialing sending data faster than its estimated bandwdith to see if throughput increases. If it does, the bottleneck bandwidth estimate (BtlBw) is updated. Knowing the maximum bandwidth and minimum latency lets it accurately calculate the exact BDP. 

### BBR versus other algorithms
BBR outperforms other congestion control algorithms when it comes to low latency and handling of Wi-Fi loss. Rather than pushing the network until it breaks, BBR gently probes the network limits and stays just below them.

### BBR issue on Windows
As aforementioned, BBR on Windows machines causes TCP FIN to be withheld on loopback connections when the payload is less than ~32 KB. The payload is delivered immediately, only the FIN packet is delayed until (and if) an RTO releases it. 

The threshold for the payload size seems to indicate that _<= ~32 KB hang_, whilst _>= ~36 KB deliver_ as intended. This seems to only happen on loopback addresses that take the loopback fast path, and does not involve the NIC. 

Interestingly enough, some HTTP requests are unaffected by this because they rely on Content-Length or Keep-Alive responses to determine when the client should stop reading; they do not rely on the FIN packet. This is unlike close-delimited responses (lacking Content-Length), which are used by HTTP/1.0, SSE/streaming, and proxies. These read upstream until EOF; here the end of body signal is FIN. This can make the issue appear sporadic. 

### Possible hypothesis
My best guess on why this bug occurs is that this is some form of pacing/segmentation mis-interaction. Perhaps BBR’s pacer mis-schedules the final small segment, leaving a trailing FIN parked until an RTO forces it out.

### Alternate fixes
If disabling large loopback MTU is not an option, there are 2 options that will work, but are not recommended due to degrading network performance. If you have control over the application, use option 2.

#### Option 1 (global)
A compromise fix is to disable TCP receive-window auto-tuning:
```ps1
netsh int tcp set gl autotuninglevel=disable
```

This pins a smaller, fixed received window, which influences the pacing algorithm’s outcome enough to stop parking the final segment. This however degrades receive-window throughput, and is generally not the right fix. 

#### Option 2 (specific)
Additionally, setting client **SO_RCVBUF** can opt the socket out of auto-tuning without disabling it globally.

