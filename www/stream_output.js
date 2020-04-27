// stream_output.js
// buffers incoming remote audio data to be sent to client speakers
class StreamOutputProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this.port.onmessage = this.onmessage.bind(this)
        //buffer to store incoming voice data
        this._buffers = {}
	//performance variables for debugging
        this._last = Date.now()
        this._avg = 0
    } 

    // message event recieved from 
    onmessage (event) {
        var temp = [];
        event.data.data.forEach(s=>{
            temp.push(s) //push each sample twice to upsample by two
            temp.push(s)
            // temp.push(s)
            // temp.push(s)

            if (temp.length == 128) {
                
		//if buffer is full push data to users databuffer
                if ( !(event.data.owner in this._buffers) )
                    this._buffers[event.data.owner] = []

                this._buffers[event.data.owner].push(temp)

                temp = []
            }
        })

	// debugging logs and value updates
        // console.log(this._buffers[event.data.owner].length)

        this._avg = 0.99 * this._avg + 0.01 * (Date.now() - this._last)
        this._last = Date.now()
    }

    process (inputs, outputs, parameters) {
        const output = outputs[0]
        if (Object.keys(this._buffers).length > 0) {
            var data = null;
            for (var key in this._buffers) {
		// for each user that has audio available
                if (this._buffers[key].length > 0)
                    if (data == null)
			//if data hasn't been processed yet then set data to the current users oldest audio segment
                        data = this._buffers[key].shift()
                    else {
			//sum the audio segment with the current users audio
                        var next = this._buffers[key].shift();
                        data.forEach((e,i)=>{
                            data[i] += next[i];
                        })
                    }        
                //clear buffers that are longer than 1 second long at sampling rate of 44100 (does not neccsarily have to be 44100)
                if (this._buffers[key].length > (44100 / 128))
                    this._buffers[key] = []
            }

	    //write data to output buffer
            if (data != null)
                output.forEach(channel => {
                    for (let i = 0; i < channel.length; i++) {
                        channel[i] = data[i];
                    }
                })
        } else {
	    //if no audio is available then write 0s to the buffer
            output.forEach(channel => {
                for (let i = 0; i < channel.length; i++) {
                    channel[i] = 0;
                }
            })
        }

        return true
    }
  }
  
  registerProcessor('stream-output-processor', StreamOutputProcessor)
