package expo.modules.semaphore

import android.system.Os
import android.util.Base64
import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import uniffi.mopro.Group
import uniffi.mopro.Identity
import uniffi.mopro.generateSemaphoreProof
import uniffi.mopro.verifySemaphoreProof

/**
 * Offline known-answer test for the native Semaphore bindings (T-589/T-590).
 *
 * The test APK declares no INTERNET permission: a successful proof shows the bundled, hash-pinned
 * zkey is used and semaphore-rs never reaches its download branch. Expected values were measured on
 * arm64 with JNA 5.13.0 and 5.19.1 (identical, see .fleet/reports/T-589.md). Test keys only.
 */
@RunWith(AndroidJUnit4::class)
class SemaphoreKatTest {
  private val ctx get() = InstrumentationRegistry.getInstrumentation().targetContext
  private lateinit var dir: File

  private fun hex(bytes: ByteArray) = bytes.joinToString("") { "%02x".format(it) }

  @Before
  fun freshProverDir() {
    dir = File(ctx.filesDir, "semaphore-prover-kat").apply { deleteRecursively(); mkdirs() }
    Os.setenv("TMPDIR", dir.absolutePath, true)
  }

  @Test
  fun deterministicOutputsAndOfflineProofWithBundledZkey() {
    BundledZkey.ensure(ctx, dir)

    val identity = Identity("ekklesia-t589-kat-identity-0001".toByteArray())
    val member = Identity("ekklesia-t589-kat-member-00002".toByteArray())
    val group = Group(listOf(identity.toElement(), member.toElement()))

    assertEquals("13039324901019702972773206202158736942226254652756759723070356519412895005527", identity.commitment())
    assertEquals("1278416703087048097084365882753100309299194802003057370991629714194279413164", identity.secretScalar())
    assertEquals("573b5b5b84db2b1f5c65a58b38f2ec934ca4f1c19936242919f39a3c11ffd31c", hex(identity.toElement()))
    assertEquals("20929549050896981976624734380217218592806713941269667443382802033625436197449", member.commitment())
    assertEquals("15212f85cde8d24615e0c4733e81f01424617ebc128664f046b0b88e50c14f01", hex(group.root() ?: ByteArray(0)))

    val proof = generateSemaphoreProof(identity, group, "t590-kat-message", "t590-kat-scope", BundledZkey.DEPTH.toUShort())
    BundledZkey.requireSupportedDepth(BundledZkey.depthOf(proof))
    assertTrue(verifySemaphoreProof(proof))
    Log.i("SEMKAT", "proofB64=" + Base64.encodeToString(proof.toByteArray(), Base64.NO_WRAP))
  }

  @Test
  fun alteredZkeyIsReplacedBeforeUse() {
    File(dir, BundledZkey.FILE_NAME).writeText("not a zkey")
    assertFalse(BundledZkey.matches(File(dir, BundledZkey.FILE_NAME)))

    val placed = BundledZkey.ensure(ctx, dir)

    assertTrue(BundledZkey.matches(placed))
    assertFalse(File(dir, BundledZkey.FILE_NAME + ".tmp").exists())
  }

  @Test
  fun foreignDepthIsRejectedBeforeTheProver() {
    assertThrows(BundledZkey.ZkeyException::class.java) { BundledZkey.requireSupportedDepth(20) }
    assertEquals(20, BundledZkey.depthOf("""{"merkle_tree_depth":20}"""))
    assertEquals(-1, BundledZkey.depthOf("not json"))
  }
}
