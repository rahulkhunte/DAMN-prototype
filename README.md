# DAMN – Decentralized AI Memory Network

![Contract Verification](demos/contract_verification.png)

## 📌 Project Status
- Core DAMN system: Implemented and deployed  
- Multi-agent demo: Completed  
- TiHAN proposal: In preparation  
- Annexure-B endorsement: Pending (institutional process)

---

## Overview
DAMN enables autonomous AI agents and robots to **store, share, and reuse learned experiences** without catastrophic forgetting.  
Built on **Ethereum + IPFS** for decentralized, persistent memory across agents.

---

## 🎯 Problem Solved
**Catastrophic Forgetting:**  
AI systems lose previously learned behaviors when trained on new tasks. DAMN creates a persistent, shared memory layer across all agents so knowledge is never lost.

---

## 🏗️ Architecture
- **IPFS:** Decentralized storage for memory data  
- **Ethereum:** Immutable ledger storing IPFS hashes  
- **Smart Contract:** Access control and ownership tracking  

---

## 🚀 Live Deployment
- **Network:** Ethereum Sepolia Testnet  
- **Contract:**  
  [`0xacAABF9A47d1Df7f2f698ad9033da10CD374B8c4`](https://sepolia.etherscan.io/address/0xacAABF9A47d1Df7f2f698ad9033da10CD374B8c4)  
- **Verified:**  
  ✅ [Sourcify](https://repo.sourcify.dev/) | [Blockscout](https://eth-sepolia.blockscout.com/)  
- **Status:** Operational (2+ memories stored)

![Multi-Agent Demo](demos/multi_agent_demo.png)

---

## 📊 Demo Results

### Scenario: UAV Obstacle Avoidance
1. **UAV-001** encounters a building obstacle at (28.61°N, 77.21°E)  
2. Learns safe maneuver: `climb_to_200m_then_proceed`  
3. Stores experience on IPFS + Blockchain  
4. **UAV-002** approaches same area  
5. Retrieves UAV-001’s memory  
6. Successfully navigates using learned behavior  
7. **Success rate:** 98% ✅  

**Result:** Zero retraining required. Knowledge persists across agent swarm.

![Network Statistics](demos/network_stats.png)

---

## 🛠️ Tech Stack
- **Smart Contract:** Solidity 0.8.0  
- **Blockchain:** Ethereum (Sepolia Testnet)  
- **Storage:** IPFS via Pinata  
- **Integration:** Python + Web3.py  
- **Infrastructure:** Lightning AI (T4 GPU)  

---

## 🎬 Quick Start

### Prerequisites
- **Sepolia ETH:** https://sepoliafaucet.com  
- **Pinata Account:** https://pinata.cloud  

### Setup
```bash
# Clone repo
git clone https://github.com/rahulkhunte/DAMN-prototype.git
cd DAMN-prototype

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with your credentials

# Run demo
jupyter notebook demo.ipynb
```
## 📁 Repository Structure
```text
DAMN-prototype/
├── README.md
├── DAMN.sol
├── demo.ipynb
├── requirements.txt
├── .env.example
├── .gitignore
└── demos/
    ├── blockchain_transaction.png
    ├── contract_verification.png
    ├── ipfs_storage.png
    ├── multi_agent_demo.png
    └── network_stats.png
```

## 🎯 Use Cases
Autonomous Drones: Swarm coordination without central server

Robotics: Manufacturing robots sharing assembly techniques

Healthcare: Surgical robots learning from collective experiences

Space Exploration: Mars rovers sharing terrain navigation data

Smart Cities: IoT devices learning optimal traffic patterns

## 🔬 TiHAN IIT Hyderabad R&D Proposal
This project is being prepared for submission to
TiHAN – IIT Hyderabad under autonomous systems research.

Proposed Goals

Optimize retrieval latency to <100ms

Implement memory quality scoring

Scale to 100+ agent networks

Deploy on TiHAN UAV testbed

## 📈 Roadmap

 Smart contract deployment (Jan 8, 2026)

 Multi-agent demo (Jan 9, 2026)

 Contract verification (Sourcify, Blockscout, Routescan)

 Memory quality scoring system

 Real-time retrieval optimization

 Hardware UAV integration (TiHAN testbed)

 Mainnet deployment

## 🧬 Q-DAMN: Quantum-Ready Extension (Future Work)

DAMN is designed to be quantum-ready.

In future research phases, we will explore hybrid quantum–classical methods
to enhance DAMN through:

- Post-quantum cryptography for memory authentication  
- Quantum-inspired optimization for memory retrieval  
- Hybrid simulation using Qiskit and quantum simulators  

Status:
- DAMN: Implemented and deployed  
- Q-DAMN: Research-phase extension (not production yet)

📄 License
MIT License
---

## 👤 Developer

**Rahul Khunte**
AI/ML & Blockchain Developer | B.Tech Civil Engineering (2022) | BIT Raipur

📧 Email: rahulk.rk903@gmail.com

🔗 GitHub: https://github.com/rahulkhunte

🌐 Portfolio: https://rahulkhunte.github.io/portfolio/  

---

## 🙏 Acknowledgments

- TiHAN – IIT Hyderabad (for research opportunity)  
- Lightning AI (for GPU compute)  
- Ethereum Foundation (Sepolia testnet)  
- Pinata (IPFS infrastructure)  

Built for **TiHAN IIT Hyderabad R&D Proposal | January 2026**

