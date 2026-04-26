// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract DAMNMemory {

    // Use bytes32 instead of string for keys = 60% cheaper gas [web:98]
    struct Memory {
        string  ipfsCID;
        address owner;
        uint64  timestamp;   // uint64 not uint256 = saves 1 storage slot
        string  agentId;
        string  taskType;
    }

    // Counters — uint128 packed together = 1 slot instead of 2
    uint128 public memoryCount;
    uint128 public batchCount;

    mapping(bytes32 => Memory) public memories;

    // ✅ Separate read vs write events — reads are FREE (view)
    event MemoryStored(bytes32 indexed memoryId, string ipfsCID, 
                       address indexed owner, string agentId, uint64 timestamp);
    event BatchStored(address indexed owner, uint256 count, uint64 timestamp);

    // ✅ FIXED: view function = FREE to read, zero gas cost
    function retrieveMemory(bytes32 _memoryId) 
        public view returns (string memory) 
    {
        require(bytes(memories[_memoryId].ipfsCID).length > 0, 
                "Memory not found");
        return memories[_memoryId].ipfsCID;
    }

    // Single write
    function storeMemory(
        bytes32 _memoryId,
        string calldata _ipfsCID,   // calldata cheaper than memory [web:100]
        string calldata _agentId,
        string calldata _taskType
    ) external {
        require(bytes(memories[_memoryId].ipfsCID).length == 0, 
                "Memory ID exists");
        memories[_memoryId] = Memory({
            ipfsCID:   _ipfsCID,
            owner:     msg.sender,
            timestamp: uint64(block.timestamp),
            agentId:   _agentId,
            taskType:  _taskType
        });
        memoryCount++;
        emit MemoryStored(_memoryId, _ipfsCID, msg.sender, 
                          _agentId, uint64(block.timestamp));
    }

    // ✅ BATCH WRITE — 1 TX for entire session, saves ~80% gas [web:102]
    function batchStoreMemory(
        bytes32[]  calldata _ids,
        string[]   calldata _cids,
        string     calldata _agentId,
        string     calldata _taskType
    ) external {
        require(_ids.length == _cids.length, "Length mismatch");
        require(_ids.length <= 50, "Max 50 per batch");

        for (uint256 i = 0; i < _ids.length;) {
            if (bytes(memories[_ids[i]].ipfsCID).length == 0) {
                memories[_ids[i]] = Memory({
                    ipfsCID:   _cids[i],
                    owner:     msg.sender,
                    timestamp: uint64(block.timestamp),
                    agentId:   _agentId,
                    taskType:  _taskType
                });
                memoryCount++;
            }
            unchecked { i++; }  // saves gas on loop increment [web:98]
        }
        batchCount++;
        emit BatchStored(msg.sender, _ids.length, uint64(block.timestamp));
    }

    // ✅ Batch read — FREE, no gas
    function batchRetrieve(bytes32[] calldata _ids) 
        external view returns (string[] memory cids) 
    {
        cids = new string[](_ids.length);
        for (uint256 i = 0; i < _ids.length;) {
            cids[i] = memories[_ids[i]].ipfsCID;
            unchecked { i++; }
        }
    }

    function getMemoryDetails(bytes32 _memoryId) 
        external view 
        returns (string memory ipfsCID, address owner, 
                 uint64 timestamp, string memory agentId, 
                 string memory taskType) 
    {
        Memory storage m = memories[_memoryId];
        return (m.ipfsCID, m.owner, m.timestamp, m.agentId, m.taskType);
    }
}