package expo.modules.semaphore

import android.content.Context
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.security.MessageDigest
import org.json.JSONObject

/**
 * Places the bundled, hash-pinned Semaphore depth-16 proving key where semaphore-rs looks for it.
 *
 * semaphore-protocol 0.1.0 (`utils.rs::download_zkey`) reads `$TMPDIR/semaphore-4.13.0-<depth>.zkey`
 * and downloads it only when the file is missing. Verifying (and, if needed, atomically restoring)
 * the file before every generate/verify keeps the network branch unreachable and fails closed on a
 * missing or altered artifact. Provenance: `zk-artifacts.manifest.json` (CODEX SECURITY-VOTUM ZK-ZKEY).
 */
object BundledZkey {
  const val DEPTH = 16
  const val FILE_NAME = "semaphore-4.13.0-16.zkey"
  const val ASSET_PATH = "semaphore/$FILE_NAME"
  const val SIZE = 3_408_199L
  const val SHA256 = "948763c7315a337b7722c0344a28af4be66fbbc618474d6dbe9036e799d1a3b5"

  class ZkeyException(message: String) : IOException(message)

  fun proverDir(context: Context): File {
    val dir = File(context.filesDir, "semaphore-prover")
    if (!dir.isDirectory && !dir.mkdirs()) {
      throw ZkeyException("Unable to create Semaphore prover storage directory.")
    }
    return dir
  }

  /** Returns `dir/FILE_NAME` after confirming size and SHA-256; restores it from the APK asset otherwise. */
  fun ensure(context: Context, dir: File): File {
    val target = File(dir, FILE_NAME)
    if (matches(target)) return target

    // Unique per call, so concurrent generate/verify calls never share a partially written file.
    val tmp: File
    try {
      tmp = File.createTempFile("$FILE_NAME.", ".tmp", dir)
    } catch (e: IOException) {
      throw ZkeyException("Unable to stage the Semaphore proving key: ${e.message}")
    }
    val digest = MessageDigest.getInstance("SHA-256")
    var size = 0L
    try {
      context.assets.open(ASSET_PATH).use { input ->
        FileOutputStream(tmp).use { out ->
          val buffer = ByteArray(64 * 1024)
          while (true) {
            val read = input.read(buffer)
            if (read < 0) break
            digest.update(buffer, 0, read)
            out.write(buffer, 0, read)
            size += read
          }
          out.fd.sync()
        }
      }
    } catch (e: IOException) {
      tmp.delete()
      throw ZkeyException("Bundled Semaphore proving key is not available: ${e.message}")
    }
    if (size != SIZE || hex(digest.digest()) != SHA256) {
      tmp.delete()
      throw ZkeyException("Bundled Semaphore proving key failed its integrity check.")
    }
    if (!tmp.renameTo(target) || !matches(target)) {
      tmp.delete()
      throw ZkeyException("Unable to install the Semaphore proving key.")
    }
    return target
  }

  fun matches(file: File): Boolean = file.isFile && file.length() == SIZE && sha256(file) == SHA256

  fun requireSupportedDepth(depth: Int) {
    if (depth != DEPTH) {
      throw ZkeyException("Unsupported Merkle tree depth $depth; only depth $DEPTH is bundled.")
    }
  }

  /** Merkle tree depth declared by a proof JSON (semaphore-rs `merkle_tree_depth`), or -1 if absent. */
  fun depthOf(proofJson: String): Int =
    try {
      JSONObject(proofJson).optInt("merkle_tree_depth", -1)
    } catch (e: Exception) {
      -1
    }

  private fun sha256(file: File): String {
    val digest = MessageDigest.getInstance("SHA-256")
    file.inputStream().use { input ->
      val buffer = ByteArray(64 * 1024)
      while (true) {
        val read = input.read(buffer)
        if (read < 0) break
        digest.update(buffer, 0, read)
      }
    }
    return hex(digest.digest())
  }

  private fun hex(bytes: ByteArray) = bytes.joinToString("") { "%02x".format(it) }
}
