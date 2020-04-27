// stream_input.js
// buffer incoming microphone data for sending to remote server
class StreamInputProcessor extends AudioWorkletProcessor {
    constructor() {
        super();

        this._buffer = []
        this._buffer_size = 2048

    }

    process (inputs, outputs, parameters) {
        const input = inputs[0];

	// append the microphone audio to the thread buffer
        this._buffer = this._buffer.concat( Array.prototype.slice.call(input[0]) );
        
	// if the audio buffer is full then send to the main thread for websocket messaging
        if (this._buffer.length >= this._buffer_size) {
            //downsample by 2
            var outbuff = this._buffer.filter((element, index) => {
                return index % 2 === 0;
            })
            
            this.port.postMessage({data:outbuff});
            this._buffer = []
        }

        return true
    }

  }
  
  registerProcessor('stream-input-processor', StreamInputProcessor)
