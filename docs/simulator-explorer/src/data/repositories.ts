// The three repositories that hold the code shown in the diagram. Each
// diagram box is colored by the repository of its code (see index.css for
// the --repo-* colors).

export type RepositoryId = "harness" | "sfv" | "fikore";

export interface Repository {
  shortName: string;
  fullName: string;
  location: string;
}

export const REPOSITORIES: Record<RepositoryId, Repository> = {
  harness: {
    shortName: "harness",
    fullName: "cap-csp-collaboration-test-pilot",
    location: "this repository (capcsp/)",
  },
  sfv: {
    shortName: "SFV",
    fullName: "SFV-Reference-Implementation",
    location: "submodule sfv-reference-implementation/",
  },
  fikore: {
    shortName: "FikoRE",
    fullName: "5g-network-emulator",
    location: "submodule 5g-network-emulator/ (FikoRE and fikore_transport)",
  },
};
