export type HRRClusteringRequest = {
  nClusters: number;
  order: number;
  nesting: number;
  sameActivities: string[][];
  ignoredActivities: string[];
  mustLink: [number, number][];
  cannotLink: [number, number][];
  previousClusters: { [bid: number]: number };
  fromScratch: boolean;
};

export type WhyActivity = {
  activity: string;
  here: number;
  elsewhere: number;
  moreCommonHere: boolean;
};

export type HRRClusterInfo = {
  size: number;
  rest: number;
  why: WhyActivity[];
  counts: { [activity: string]: [number, number] };
};

export type HRRClusteringResult = {
  clusters: number[][];
  noActivities: number[];
  info: HRRClusterInfo[];
  canonical: { [activity: string]: string };
  setAside: [number, number][];
  fromScratch: boolean;
  moved: number | null;
  seconds: { encode: number; cluster: number; describe: number; total: number };
};
