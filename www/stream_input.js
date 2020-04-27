// stream_input.js
// buffer incoming microphone data for sending to remote server
class StreamInputProcessor extends AudioWorkletProcessor {
    constructor() {
        super();

        this._buffer = []
        this._buffer_size = 2048

        // this._resampler = new Resampler(44100, 48000, 1, this._buffer_size);
    }

    process (inputs, outputs, parameters) {
        const input = inputs[0];

        this._buffer = this._buffer.concat( Array.prototype.slice.call(input[0]) );
        
        if (this._buffer.length >= this._buffer_size) {
            //downsample 
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
