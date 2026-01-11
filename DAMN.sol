// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract DAMNMemory {
    struct Memory {
        string ipfsCID;
        address owner;
        uint256 timestamp;
        string agentId;
        string taskType;
    }
    
    mapping(string => Memory) public memories;
    string[] public memoryIds;
    
    event MemoryStored(string indexed memoryId, string ipfsCID, address indexed owner, string agentId, uint256 timestamp);
    event MemoryAccessed(string indexed memoryId, address indexed accessor, uint256 timestamp);
    
    function storeMemory(string memory _memoryId, string memory _ipfsCID, string memory _agentId, string memory _taskType) public {
        require(bytes(memories[_memoryId].ipfsCID).length == 0, "Memory ID already exists");
        
        memories[_memoryId] = Memory({
            ipfsCID: _ipfsCID,
            owner: msg.sender,
            timestamp: block.timestamp,
            agentId: _agentId,
            taskType: _taskType
        });
        
        memoryIds.push(_memoryId);
        emit MemoryStored(_memoryId, _ipfsCID, msg.sender, _agentId, block.timestamp);
    }
    
    function retrieveMemory(string memory _memoryId) public returns (string memory) {
        require(bytes(memories[_memoryId].ipfsCID).length > 0, "Memory does not exist");
        emit MemoryAccessed(_memoryId, msg.sender, block.timestamp);
        return memories[_memoryId].ipfsCID;
    }
    
    function getMemoryDetails(string memory _memoryId) public view returns (string memory ipfsCID, address owner, uint256 timestamp, string memory agentId, string memory taskType) {
        Memory memory m = memories[_memoryId];
        return (m.ipfsCID, m.owner, m.timestamp, m.agentId, m.taskType);
    }
    
    function getMemoryCount() public view returns (uint256) {
        return memoryIds.length;
    }
}
