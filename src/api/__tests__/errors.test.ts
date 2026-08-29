import * as Network from "expo-network";
import { classifyFetchFailure, NetworkError, UnreachableError } from "../errors";

jest.mock("expo-network", () => ({
  getNetworkStateAsync: jest.fn(),
}));

const mockedGetNetworkStateAsync = Network.getNetworkStateAsync as jest.Mock;

describe("classifyFetchFailure", () => {
  afterEach(() => {
    mockedGetNetworkStateAsync.mockReset();
  });

  it("returns NetworkError when the device is offline", async () => {
    mockedGetNetworkStateAsync.mockResolvedValue({
      isConnected: false,
      isInternetReachable: false,
    });

    const error = await classifyFetchFailure();

    expect(error).toBeInstanceOf(NetworkError);
  });

  it("returns UnreachableError when the device is online but the request still failed", async () => {
    mockedGetNetworkStateAsync.mockResolvedValue({
      isConnected: true,
      isInternetReachable: true,
    });

    const error = await classifyFetchFailure();

    expect(error).toBeInstanceOf(UnreachableError);
  });

  it("defaults to UnreachableError when connectivity is inconclusive", async () => {
    mockedGetNetworkStateAsync.mockResolvedValue({
      isConnected: undefined,
      isInternetReachable: undefined,
    });

    const error = await classifyFetchFailure();

    expect(error).toBeInstanceOf(UnreachableError);
  });

  it("defaults to UnreachableError when the connectivity check itself throws", async () => {
    mockedGetNetworkStateAsync.mockRejectedValue(new Error("native module unavailable"));

    const error = await classifyFetchFailure();

    expect(error).toBeInstanceOf(UnreachableError);
  });
});
