import at.unisalzburg.dbresearch.apted.costmodel.StringUnitCostModel;
import at.unisalzburg.dbresearch.apted.distance.APTED;
import at.unisalzburg.dbresearch.apted.node.Node;
import at.unisalzburg.dbresearch.apted.node.StringNodeData;
import at.unisalzburg.dbresearch.apted.parser.BracketStringInputParser;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.List;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Unit-cost tree edit distance (APTED, Pawlik and Augsten) between many trees, in parallel.
 *
 *   java AllPairs TREES OUT THREADS            every pair i < j, in numpy.triu_indices order
 *   java AllPairs TREES OUT THREADS PAIRS      the pairs listed in PAIRS
 *
 * TREES holds one tree per line in bracket notation ({a{b}{c}}).  PAIRS holds big-endian int32
 * pairs (i, j).  OUT receives one big-endian int32 distance per pair: with unit costs every
 * distance is a whole number.
 */
public class AllPairs {

    private static final int BLOCK = 512;

    public static void main(String[] args) throws Exception {
        List<String> lines = Files.readAllLines(Paths.get(args[0]));
        BracketStringInputParser parser = new BracketStringInputParser();
        @SuppressWarnings("unchecked")
        Node<StringNodeData>[] trees = new Node[lines.size()];
        for (int i = 0; i < trees.length; i++) {
            trees[i] = parser.fromString(lines.get(i));
        }
        int threads = Integer.parseInt(args[2]);
        int[] ia, ib;
        if (args.length > 3) {
            int[][] p = readPairs(args[3]);
            ia = p[0];
            ib = p[1];
        } else {
            int n = trees.length;
            long m = (long) n * (n - 1) / 2;
            ia = new int[(int) m];
            ib = new int[(int) m];
            int k = 0;
            for (int i = 0; i < n; i++) {
                for (int j = i + 1; j < n; j++) {
                    ia[k] = i;
                    ib[k++] = j;
                }
            }
        }
        int[] out = new int[ia.length];
        AtomicLong next = new AtomicLong();
        Thread[] pool = new Thread[threads];
        for (int t = 0; t < threads; t++) {
            pool[t] = new Thread(() -> {
                APTED<StringUnitCostModel, StringNodeData> apted = new APTED<>(new StringUnitCostModel());
                long start;
                while ((start = next.getAndAdd(BLOCK)) < ia.length) {
                    int end = (int) Math.min(start + BLOCK, ia.length);
                    for (int k = (int) start; k < end; k++) {
                        out[k] = Math.round(apted.computeEditDistance(trees[ia[k]], trees[ib[k]]));
                    }
                }
            });
            pool[t].start();
        }
        for (Thread t : pool) {
            t.join();
        }
        try (DataOutputStream o = new DataOutputStream(new BufferedOutputStream(new FileOutputStream(args[1])))) {
            for (int d : out) {
                o.writeInt(d);
            }
        }
    }

    private static int[][] readPairs(String path) throws IOException {
        long bytes = Files.size(Paths.get(path));
        int m = (int) (bytes / 8);
        int[] ia = new int[m], ib = new int[m];
        try (DataInputStream in = new DataInputStream(new BufferedInputStream(new FileInputStream(path)))) {
            for (int k = 0; k < m; k++) {
                ia[k] = in.readInt();
                ib[k] = in.readInt();
            }
        }
        return new int[][] {ia, ib};
    }
}
