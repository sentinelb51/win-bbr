# win-bbr
Properly using the BBRv2 TCP congestion control algorithm on Windows

### What is a congestion control algorithm
When you send data over a network, it is [split into small packages called "packets"](https://en.wikipedia.org/wiki/Packet_switching), which travel through a series of computers (routers) to reach a destination. The network is a shared resource between multiple computers, and network performance can thus be constrained by factors like bandwidth and latency. When this happens, intermediary routers can be overwhelmed, causing packet loss. Packet loss hurts network performance because data has to be re-transmitted again, wasting bandwidth and time. 

A congestion control algorithm is software typically within an operating system that decides how fast to send packets into the network. These algorithms calculate a "Bandwidth-Delay Product" (BDP) by multiplying bandwidth (bits/sec) by round-trip-time (rtt; seconds), which is the total volume of data that can exist in-flight. Ideally, the algorithm tries to match the BDP as closely as possible; sending less than BDP is underutilising the link; sending more than BDP is overutilising. 

### The challenge
Measuring BDP accurately is tricky; to measure true minimum RTT, the network pipe must be completely empty, yet to measure maximum bandwidth, the network pipe must be completely full. 

### What is BBR
BBR stands for "Bottleneck Bandwidth and RTT" and was developed by Google in 2016. Unlike other algorithms, it is not a loss-based algorithm, but rather builds an internal mathematical model of the network to estimate capacity. BBR periodically reduces the amount of data sent to drain queues and measure true physical latency (RTprop), as well as trialing sending data faster than its estimated bandwdith to see if throughput increases. If it does, the bottleneck bandwidth estimate (BtlBw) is updated. Knowing the maximum bandwidth and minimum latency lets it accurately calculate the exact BDP. 

### BBR versus other algorithms
BBR outperforms other congestion control algorithms when it comes to low latency and handling of Wi-Fi loss. Rather than pushing the network until it breaks, BBR gently probes the network limits and stays just below them.

### The fix

### Alternate fix (less optimal)

### Dev notes
