class mappedRegion(object):
    def __init__(self, tstart, hostbase, accbase, bsize):
        self.map_time = tstart
        self.unmap_time = -1
        self.host = hostbase
        self.acc = accbase
        self.size = bsize
    def __repr__(self):
        return "Region at host address %s of size %d B mapped to device address %s from time %g to %g" %(hex(self.host), self.size, hex(self.acc), self.map_time, self.unmap_time)
    def renormalize_time(self, tstart, tend):
        self.map_time -= tstart
        if self.unmap_time > 0:
            self.unmap_time -= tstart
        else:
            self.unmap_time = tend - tstart
        

def parse_present(filename):
    import parse
    mapped = {}
    finalized = []

    with open(filename, 'r') as dbFile:
        for line in dbFile:
            if ("present table" not in line):
                continue
            if "add to" in line:
                # record looks like
                # 8559201.527394617 ACC: PE 0:            add to present table index 8: host 100005076c0 to 1000050f6c0, acc 2aab00a40000
                time = float(line.split("ACC")[0].strip())
                entry_record = line.split("add to present table index")[-1]
                ptindex = int(entry_record.split(":")[0].strip())
                hostStart_hex = entry_record.split(":")[1].strip().strip("host").split("to")[0].strip()
                hostEnd_hex = entry_record.split(":")[-1].split("to")[-1].split(",")[0].strip()
                # You must split on an 'acc' bracket by spaces, otherwise it's possible to accidentally
                # split on an 'acc' embeded in a hex memory address.
                # YES! THIS DID HAPPEN!
                accStart_hex = entry_record.split(" acc ")[-1].strip()
                if ptindex in mapped:
                    print("Present table index %d already mapped! Dropping old entry" %ptindex)
                mapped[ptindex] = mappedRegion(time, 
                                                int(hostStart_hex, 16),
                                                int(accStart_hex, 16),
                                                int(hostEnd_hex, 16) - int(hostStart_hex, 16)
                                                )
            if "last release" in line:
                # record looks like
                # 8559217.470128385 ACC: PE 0:            last release acc 2aab00bbde00 from present table index 14 (ref_count 1)
                time = float(line.split("ACC")[0].strip())
                entry_record = line.split("last release acc")[-1].strip()
                ptindex = int(entry_record.split("index")[-1].split("(")[0].strip())
                accAddr_hex = entry_record.split("from")[0].strip()
                if ptindex not in mapped:
                    raise KeyError("No mapped entry at present table index %d" %ptindex)
                accAddr_int = int(accAddr_hex, 16)
                if (accAddr_int < mapped[ptindex].acc) or (accAddr_int > (mapped[ptindex].acc + mapped[ptindex].size)):
                    print(mapped)
                    print(line)
                    raise IndexError("Last released memory address %s outside range of present table index %d (%s to %s) " %(accAddr_hex, ptindex, hex(mapped[ptindex].acc), hex(mapped[ptindex].acc + mapped[ptindex].size)))
                mapped[ptindex].unmap_time = time
                finalized.append(mapped.pop(ptindex))
    return mapped, finalized

def main():
    import argparse
    import numpy as np
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    # This import registers the 3D projection, but is otherwise unused.
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 unused import
    parser = argparse.ArgumentParser("Parse data movement")
    parser.add_argument("infile", nargs=1, type=str, help="Timestamped input file from CRAY_ACC_DEBUG output")
    parser.add_argument("--hmax", type=str, help="Drop host addresses above this hex address",default=None)
    parser.add_argument("--mark", type=str, help="Make a specific device address in the plot",default=None)
    parser.add_argument("--dumptable", action="store_true", default=False, help="Dump table entries to stdout during plotting")
    options = parser.parse_args()

    mapped, finalized = parse_present(options.infile[0])
    if mapped == {}:
        mapped[0] = mappedRegion(np.inf, 0, 0, 0)
        mapped[0].unmap_time = 0

    mintime = min(min(mapped.values(), key=lambda x: x.map_time).map_time, min(finalized, key=lambda x: x.map_time).map_time)
    maxtime = max(max(mapped.values(), key=lambda x: x.map_time).map_time, max(finalized, key=lambda x: x.unmap_time).unmap_time)
    print(mintime, maxtime)
    #mintime = min(finalized, key=lambda x: x.map_time).map_time
    #maxtime = max(finalized, key=lambda x: x.unmap_time).unmap_time
    for entry in finalized:
        entry.renormalize_time(mintime, maxtime)
        if (options.dumptable):
            print(entry)
    for entry in mapped.values():
        entry.renormalize_time(mintime, maxtime)
        if (options.dumptable):
            print(entry)

    print(mapped)
    xvals = np.array([x.host for x in finalized],dtype=int)
    yvals = np.array([x.acc for x in finalized],dtype=int)
    bottoms = np.array([x.map_time for x in finalized])
    tops = np.array([x.unmap_time for x in finalized])
    sizes = np.array([x.size for x in finalized])
    if (options.hmax):
        thresholds = xvals <int(options.hmax,16)
        xvals = xvals[thresholds]
        yvals = yvals[thresholds]
        bottoms = bottoms[thresholds]
        tops = tops[thresholds]
        sizes = sizes[thresholds]


    nf_xvals = np.array([x.host for x in mapped.values()],dtype=int)
    nf_yvals = np.array([x.acc for x in mapped.values()],dtype=int)
    nf_bottoms = np.array([x.map_time for x in mapped.values()])
    nf_tops = np.array([x.unmap_time for x in mapped.values()])
    nf_sizes = np.array([x.size for x in mapped.values()],dtype=int)

    print(bottoms)

    fig = plt.figure(figsize=(16, 8))
    #ax1 = fig.add_subplot(121, projection='3d')
    ax2 = fig.add_subplot(111)

    #ax1.bar3d(xvals, yvals, bottoms, sizes, sizes, tops - bottoms)
    #ax1.set_xlabel("Host Address")
    #ax1.set_ylabel("Accelerator Address")
    #ax1.set_zlabel("Program time")
    #ax1.set_xscale('log',basex=2)
    #ax1.set_yscale('log',basex=2)

    ax2.bar(yvals, tops - bottoms, width=sizes, bottom=bottoms, align='edge')
    ax2.scatter(yvals, bottoms, zorder=2.5)
    ax2.bar(nf_yvals, nf_tops - nf_bottoms, width=nf_sizes, bottom=nf_bottoms, align='edge',color='red')
    ax2.scatter(nf_yvals, nf_bottoms, zorder=2.5)
 
    def to_hex(x, pos):
        return '%x' % int(x)

    fmt = ticker.FuncFormatter(to_hex)
    #ax2.get_xaxis().set_major_locator(ticker.MultipleLocator(1))
    ax2.get_xaxis().set_major_formatter(fmt)
    
    ax2.set_xlabel("Accelerator Address")
    ax2.set_ylabel("Program time")
    #ax2.set_xscale('log',basex=2)
    if(options.mark):
        plt.axvline(x=int(options.mark,16),color='red')
    plt.show()


if __name__ == "__main__":
    main()