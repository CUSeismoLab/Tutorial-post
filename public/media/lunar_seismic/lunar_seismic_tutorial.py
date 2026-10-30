"""Apollo lunar seismology tutorial using the Nunn et al. (2020) data archive.

Run from this directory after downloading the Zenodo stack archive into data/:

    python lunar_seismic_tutorial.py
    python lunar_seismic_tutorial.py --fetch-raw
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from obspy import UTCDateTime, read
from obspy.clients.fdsn import Client
from scipy.ndimage import uniform_filter1d


HERE = Path(__file__).resolve().parent
STACK_DIR = HERE / "data" / "Lognonne_et_al_2003_deep_moonquake_stacks"
FIGURE_DIR = HERE / "figures"


def load_aligned_stack(cluster: str = "A1", station: str = "S12", run: str = "st9"):
    """Read MHZ/MHX/MHY and interpolate onto their common time grid."""
    folder = STACK_DIR / cluster / station / run
    traces = []
    for channel in ("MHZ", "MHX", "MHY"):
        name = f"Lognonne_et_al_2003.{cluster}.{station}.{run}.{channel}"
        path = folder / name
        if not path.is_file():
            raise FileNotFoundError(f"Missing {path}; download and extract the Zenodo archive first.")
        traces.append(read(str(path))[0])

    start = max(tr.stats.starttime for tr in traces)
    end = min(tr.stats.endtime for tr in traces)
    if end <= start:
        raise ValueError("The three components have no overlapping time interval.")

    sampling_rate = min(tr.stats.sampling_rate for tr in traces)
    time = np.arange(int((end - start) * sampling_rate) + 1) / sampling_rate
    components = []
    for tr in traces:
        original_time = (
            tr.stats.starttime - start
            + np.arange(tr.stats.npts) / tr.stats.sampling_rate
        )
        components.append(np.interp(time, original_time, tr.data.astype(float)))

    return time, np.vstack(components), sampling_rate, start


def bandpass_components(components: np.ndarray, sampling_rate: float) -> np.ndarray:
    """Demean and bandpass the aligned stack at 0.05-1.0 Hz."""
    from obspy import Trace

    filtered = []
    for values in components:
        tr = Trace(data=values.copy(), header={"sampling_rate": sampling_rate})
        tr.detrend("demean")
        tr.detrend("linear")
        tr.filter("bandpass", freqmin=0.05, freqmax=1.0, corners=4, zerophase=True)
        filtered.append(tr.data)
    return np.vstack(filtered)


def rectilinearity(components: np.ndarray, sampling_rate: float,
                  window_seconds: float = 10.0) -> np.ndarray:
    """Compute an orientation-independent, three-component polarization weight."""
    width = max(3, int(round(window_seconds * sampling_rate)) | 1)
    means = np.vstack([uniform_filter1d(row, size=width) for row in components])
    covariance = np.empty((components.shape[1], 3, 3), dtype=float)
    for i in range(3):
        for j in range(3):
            product_mean = uniform_filter1d(components[i] * components[j], size=width)
            covariance[:, i, j] = product_mean - means[i] * means[j]
    eigenvalues = np.linalg.eigvalsh(covariance)  # ascending order
    largest = np.maximum(eigenvalues[:, 2], np.finfo(float).eps)
    weight = 1.0 - (eigenvalues[:, 0] + eigenvalues[:, 1]) / (2.0 * largest)
    return np.clip(weight, 0.0, 1.0)


def plot_stacks(time: np.ndarray, raw: np.ndarray, filtered: np.ndarray,
                weight: np.ndarray) -> None:
    FIGURE_DIR.mkdir(exist_ok=True)
    fig, axes = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
    for ax, values, label in zip(axes, raw, ("MHZ", "MHX", "MHY")):
        ax.plot(time, values, color="black", linewidth=0.55)
        ax.set_ylabel(label)
        ax.grid(alpha=0.2)
    axes[-1].set_xlabel("Time from common start (s)")
    fig.suptitle("A1 / S12 / st9 stacked waveforms")
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / "stacked_three_components.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(10, 5), sharex=True)
    axes[0].plot(time, filtered[0], color="#58708d", linewidth=0.6,
                 label="Bandpassed MHZ")
    axes[0].plot(time, filtered[0] * weight, color="#b04a3f", linewidth=0.65,
                 label="Polarization-weighted MHZ")
    axes[0].legend(loc="upper right")
    axes[0].set_ylabel("Relative amplitude")
    axes[1].plot(time, weight, color="#344d6c", linewidth=0.65)
    axes[1].set_ylabel("Weight")
    axes[1].set_xlabel("Time from common start (s)")
    axes[1].set_ylim(-0.05, 1.05)
    for ax in axes:
        ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / "polarization_weight.png", dpi=180)
    plt.close(fig)


def check_catalog() -> None:
    catalog = HERE / "data" / "levent.1008c"
    if not catalog.is_file():
        print("Catalog not found; skip the optional catalog check.")
        return
    events = []
    with catalog.open(encoding="ascii", errors="replace") as stream:
        for line in stream:
            if len(line) >= 80 and line[2:4].strip().isdigit():
                events.append({
                    "year": int(line[2:4]), "day": int(line[5:8]),
                    "time": line[9:13].strip(),
                })
    example = any(e == {"year": 71, "day": 4, "time": "1651"}
                  for e in events)
    print(f"Catalog: {len(events)} events; 1971 day 004 16:51 event present: {example}")


def fetch_raw_waveform() -> None:
    """Retrieve and response-correct one Apollo 12 waveform from EarthScope."""
    start = UTCDateTime("1971-01-04T16:51:00")
    client = Client("EARTHSCOPE")
    stream = client.get_waveforms("XA", "S12", "00", "MHZ", start, start + 900)
    inventory = client.get_stations(
        network="XA", station="S12", location="00", channel="MHZ",
        starttime=start, endtime=start + 900, level="response",
    )
    trace = stream[0].copy()
    trace.detrend("demean")
    trace.detrend("linear")
    trace.taper(max_percentage=0.05)
    trace.remove_response(inventory=inventory, output="DISP",
                          pre_filt=(0.001, 0.005, 1.0, 2.0), water_level=60)
    FIGURE_DIR.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.plot(trace.times(), trace.data, color="black", linewidth=0.6)
    ax.set(xlabel="Time from 1971-01-04 16:51 UTC (s)",
           ylabel="Displacement (m)", title="Apollo 12 raw event: XA.S12.00.MHZ")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / "raw_earthscope_event.png", dpi=180)
    plt.close(fig)
    print(f"EarthScope waveform: {trace.id}, {trace.stats.npts} samples")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch-raw", action="store_true",
                        help="also fetch and plot a single raw Apollo waveform")
    args = parser.parse_args()
    time, raw, sampling_rate, start = load_aligned_stack()
    filtered = bandpass_components(raw, sampling_rate)
    weight = rectilinearity(filtered, sampling_rate)
    plot_stacks(time, raw, filtered, weight)
    print(f"Aligned A1/S12/st9: {raw.shape[1]} samples at {sampling_rate:.4f} Hz")
    print(f"Common start: {start}")
    print(f"Saved figures in {FIGURE_DIR}")
    check_catalog()
    if args.fetch_raw:
        fetch_raw_waveform()


if __name__ == "__main__":
    main()
