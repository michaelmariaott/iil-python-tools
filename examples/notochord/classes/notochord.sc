// MIDI output API

NotoOutput {
	var <port, <sema, <nAnon;
    *new { | deviceName=nil, portName=nil, anonInstruments=32 |
        ^super.new.init(deviceName, portName, anonInstruments)
    }

    init { | deviceName, portName, anonInstruments |
		MIDIClient.initialized.not.if{MIDIClient.init};
		Platform.case(
			\osx,     {
				deviceName = deviceName?"IAC Driver";
				portName = portName?"Bus 1";
			},
			\linux,   { "Notochord: TODO: default MIDI output device on Linux".postln },
			\windows, { "Notochord: TODO: default MIDI output device on Windows".postln }
		);
		nAnon = anonInstruments;
		port = MIDIOut.newByName(deviceName, portName).latency_(0);
		sema = Semaphore(1);
    }

	releaseAll { | vel=0 |
		128.do{arg note; 16.do{arg chan;
			port.noteOff(chan, note, vel)}}
	}

	isDrum { | inst |
		inst;
		^ ((inst>128)&&(inst<=256)) || (inst>(256+nAnon))
	}
}

NotoMappingOutput : NotoOutput {
	var <>instrumentMap, <>drumMap;

	init { | deviceName, portName, anonInstruments |
		super.init(deviceName, portName, anonInstruments);
		instrumentMap = Dictionary.new;
		drumMap = Dictionary.new;
    }

	send { | inst, pitch, vel | 
		var channel;
		channel = instrumentMap.at(inst);
		(isDrum(inst) && drumMap.includesKey(pitch)).if{
			pitch = drumMap.at(pitch)};
		channel.isNil.if{
			"WARNING: unmapped instrument in NotoDAWOutput.send".postln; ^nil};
		// pitch.isNil.if{
			// "WARNING: unmapped drum in NotoDAWOutput.send".postln; ^nil};
		(vel>0).if{
			port.noteOn(channel, pitch, vel);
		}{
			port.noteOff(channel, pitch);
		};
	}
}

NotoFluidOutput : NotoOutput {
	// var <>bank_xg,
	var <channelLRU, <instChannels, <>soundFontPath;

	init { | deviceName, portName, anonInstruments |
		super.init(deviceName, portName, anonInstruments);
		// bank_xg = true;
		channelLRU = LinkedList.fill(16, {arg i; i});
		instChannels = TwoWayIdentityDictionary.new;
    }

	send { | inst, pitch, vel |
		var channel;
		sema.wait;
		// check if this instrument has a channel
		channel = instChannels.at(inst);
		channel.isNil.if{
			inst;
			// if not get least recently used channel
			channel = channelLRU.popFirst;
			// and change the bank+program
			this.isDrum(inst).if{
				// port.control(channel, 0, bank_xg.if{120}{1}); //drum
				port.control(channel, 0, 1); //drum
				port.control(channel, 32, 0);
				port.program(channel, inst-129); //program
			}{
				port.control(channel, 0, 0); //melodic
				port.control(channel, 32, 0);
				port.program(channel, inst-1); //program
			};
			// TODO: anonymous instruments?

		}{
			channelLRU.remove(channel)
		};
		// send the event
		(vel>0).if{
			port.noteOn(channel, pitch, vel);
		}{
			port.noteOff(channel, pitch);
		};
		// update the inst / channel mappings
		channelLRU.add(channel);
		instChannels.remove(channel);
		instChannels[inst] = channel;
		sema.signal;
	}

	fluidSynthCmd {
		^ "fluidsynth -v -o midi.autoconnect=1 -o synth.midi-bank-select=mma"
		+ soundFontPath.isNil.if{""}{soundFontPath.shellQuote}
	}

	startFluidSynth {
		this.fluidSynthCmd.runInTerminal
	}
}


// MIDI input API
NotoInput {
	var <deviceUID;

	*new { | deviceName, portName |
		^super.new.init(deviceName, portName)
    }

	init { | deviceName, portName |
		var device; 
		MIDIClient.initialized.not.if{MIDIClient.init};
		MIDIIn.connectAll;

		Platform.case(
			\osx,     {
				deviceName = deviceName?"IAC Driver";
			},
			\linux,   { "Notochord: TODO: default MIDI input device on Linux".postln },
			\windows, { "Notochord: TODO: default MIDI input device on Windows".postln }
		);

		device = MIDIClient.sources.detect{
			|e| e.device.containsi(deviceName) && portName.isNil.if{true}{e.device.containsi(portName)}
		};
		device.isNil.if{
			"WARNING: NotoInput: MIDI input device not found".postln;
			("available sources are: "++MIDIClient.sources).postln;
			deviceUID=0;
		}{
			("NotoInput: using MIDI input device \""++deviceName++"\"").postln;
			deviceUID=device.uid;
		}
    }

	noteOn { |fn|
		MIDIdef.noteOn(\input_on++deviceUID, fn, srcID:deviceUID).permanent_(true);
	}

	noteOff { |fn|
		MIDIdef.noteOff(\input_off++deviceUID, fn, srcID:deviceUID).permanent_(true);
	}
}


// Notochord API
Notochord {
	var <python, <>handler, <>notochordPath, <>notochordEnv, <argKeys, <pendingQueries, <>dropOldQueries;

	*new { |pythonHost="127.0.0.1", pythonPort=9999|
        ^super.new.init(pythonHost, pythonPort)
    }

    init { |pythonHost, pythonPort|
		// address to send OSC to notochord
		python = NetAddr.new(pythonHost, pythonPort);

		// handler for OSC from notochord
		OSCdef(\notochord_from_python, {
			arg msg, time, src;
			// ignore stale messages
			(pendingQueries==1 || dropOldQueries.not).if{
				handler.(Dictionary.newFrom(msg[1..]))
			};
			pendingQueries = pendingQueries - 1;
			(pendingQueries<0).if{
				"warning: pending notochord queries was <0".postln;
				pendingQueries = 0;
			};

		}, "notochord/query_return").permanent_(true);

		// initial handler which just prints the argument dict
		handler = _.postln;

		notochordEnv = "iil-python-tools"; //default conda env for notochord

		// these should be the exact keyword arguments accepted by the python API
		// Notochord.global_args will look for global variables with
		// the same names and prepare them for sending over OSC
		argKeys = [
			\allow_end,
			\min_time, \max_time, \min_vel, \max_vel,
			\include_inst, \exclude_inst,
			\allow_anon,
			\include_pitch, \exclude_pitch, \include_drum,
			\instrument_temp, \pitch_temp,
			\rhythm_temp, \timing_temp, \velocity_temp,
		];

		pendingQueries = 0;
		dropOldQueries = false;
	}

	reset { |...args|
		python.sendMsg("/notochord/reset", *args);
	}

	feed { |...args|
		python.sendMsg("/notochord/feed", *args);
	}

	query { |...args|
		python.sendMsg("/notochord/query", *args);
		pendingQueries = pendingQueries+1;
	}

	queryFeed { |...args|
		python.sendMsg("/notochord/query_feed", *args);
		pendingQueries = pendingQueries+1;
	}

	feedQuery { |...args|
		python.sendMsg("/notochord/feed_query", *args);
		pendingQueries = pendingQueries+1;
	}

	feedQueryFeed { |...args|
		python.sendMsg("/notochord/feed_query_feed", *args);
		pendingQueries = pendingQueries+1;
	}

	notochordCmd {
		var ckpt = notochordPath.notNil.if{
			"--checkpoint"+notochordPath.shellQuote}{""};
		var host_port = (
			"--host" + python.hostname
			+ "--receive_port" + python.port
		);
		^ (
			"`conda info --base`/envs/"++notochordEnv++"/bin/python"
			+ "-m notochord server"
			+ host_port
			+ ckpt
		);
	}

	startNotochord {
		this.notochordCmd.runInTerminal();
	}

	globalArgs {
		// packs any global variables with the names of Notochord
		// arguments into a List of key, value pairs
		// for use with Notochord.query etc
		var kw = List[];
		argKeys.do{arg name;
			var val = currentEnvironment[name];
			val.notNil.if{
				kw.add(name);
				// convert Collections to JSON strings
				val.isKindOf(Collection).if{
					val = "%JSON:"++JSON.stringify(val)};
				kw.add(val)}
		}
		^kw
	}

}


// Scheduler API
//
// - adapt the Tidal scheduler; handle late events properly (?)
// ... in tidal scheduler every arriving event *will* happen
// in other apps, events arrive from notochord which may be pre-empted
// there are several kinds of events:
//   -- events which will play at a specific time
//      A. complete events which are ready
//      B. incomplete events which need a trip through notochord
//   C. forecasted events which may not play
// A requires: schedule, once locked in: feed, finally play
// B requires: schedule, once locked in: query_feed, finally play
// C requires: schedule, once locked in: as A
//   -- but if anything else gets scheduled before it, cancel

// alternate view:
//
// keep a 'pending prediction'. whenever an event gets completed, replace it.
// if it ever gets locked in, schedule it and treat as a new completed event


// model: notochord is instantaneous
// schedule each event. whenever an event is played, replace prediction (e.g. cancel and reschedule it)

// model: notochord query has a fixed latency
// issue: a prediction can be invalidated before it returns,
//        causing the next query to be late (unless interruption is possible)
// issue: predicted events with less than nclatency delta will be scheduled late

// model: notochord feed has a fixed latency
// issue: events spaced less than nclatency will cause queries to be late


// idea: feed_query_time
// this would feed an event and then query *only* delta to next event
// a separate query would complete the event just-in-time, *only* if it isn't
// first pre-empted, which prevents wasting time on other attributes
// gets hairy when there are other constraints though