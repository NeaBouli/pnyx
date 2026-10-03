package expo.modules.semaphore

import android.system.Os
import android.util.Base64
import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.security.MessageDigest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import uniffi.mopro.Group
import uniffi.mopro.Identity
import uniffi.mopro.generateSemaphoreProof
import uniffi.mopro.verifySemaphoreProof

/**
 * T-589 known-answer test for the native Semaphore bindings across JNA versions.
 *
 * Deterministic outputs for a fixed test identity (commitment, secret scalar, element, group
 * root) must be identical before and after a JNA update; a proof generated with one JNA version
 * must verify with the other (pass it as instrumentation argument `crossProofB64`). Groth16 proof
 * bytes are randomized, so they are verified, not compared. Test keys only, never real users.
 */
@RunWith(AndroidJUnit4::class)
class SemaphoreKatTest {
  private fun hex(bytes: ByteArray) = bytes.joinToString("") { "%02x".format(it) }

  @Test
  fun deterministicOutputsAndProofRoundTrip() {
    val ctx = InstrumentationRegistry.getInstrumentation().targetContext
    val proverDir = File(ctx.cacheDir, "semaphore-kat").apply { mkdirs() }
    Os.setenv("TMPDIR", proverDir.absolutePath, true)

    val identity = Identity("ekklesia-t589-kat-identity-0001".toByteArray())
    val member = Identity("ekklesia-t589-kat-member-00002".toByteArray())
    val group = Group(listOf(identity.toElement(), member.toElement()))

    val values = linkedMapOf(
      "commitment" to identity.commitment(),
      "secretScalar" to identity.secretScalar(),
      "toElement" to hex(identity.toElement()),
      "memberCommitment" to member.commitment(),
      "groupRoot" to hex(group.root() ?: ByteArray(0)),
      "groupDepth" to group.depth().toString(),
    )
    values.forEach { (k, v) -> Log.i("SEMKAT", "$k=$v") }

    val expected = InstrumentationRegistry.getArguments()
    for ((k, v) in values) {
      expected.getString("expect_$k")?.let { assertEquals("KAT mismatch for $k", it, v) }
    }

    val proof = generateSemaphoreProof(identity, group, "t589-kat-message", "t589-kat-scope", 16u)
    assertTrue("own proof must verify", verifySemaphoreProof(proof))
    Log.i("SEMKAT", "proofB64=" + Base64.encodeToString(proof.toByteArray(), Base64.NO_WRAP))

    val zkey = File(proverDir, "semaphore-4.13.0-16.zkey")
    val zkeySha = hex(MessageDigest.getInstance("SHA-256").digest(zkey.readBytes()))
    Log.i("SEMKAT", "zkeySha256=$zkeySha")
    assertEquals("948763c7315a337b7722c0344a28af4be66fbbc618474d6dbe9036e799d1a3b5", zkeySha)

    expected.getString("crossProofB64")?.let { b64 ->
      val other = String(Base64.decode(b64, Base64.NO_WRAP))
      assertTrue("cross proof from the other JNA version must verify", verifySemaphoreProof(other))
      Log.i("SEMKAT", "crossVerify=true")
    }
  }
}
