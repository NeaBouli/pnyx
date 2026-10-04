package expo.modules.semaphore

import android.system.Os
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition
import expo.modules.kotlin.exception.CodedException
import uniffi.mopro.*

class ProofModule : Module() {

  /**
   * Points semaphore-rs at the app-private prover directory and installs the bundled, hash-pinned
   * zkey there before every native call, so the library never reaches its download branch.
   */
  private fun prepareProver() {
    val reactContext = appContext.reactContext
      ?: throw CodedException("ProofStorageError", "React context is not available for Semaphore prover storage.", null)
    try {
      val proofDir = BundledZkey.proverDir(reactContext)
      Os.setenv("TMPDIR", proofDir.absolutePath, true)
      BundledZkey.ensure(reactContext, proofDir)
    } catch (e: BundledZkey.ZkeyException) {
      throw CodedException("ProofStorageError", e.message ?: "Semaphore proving key unavailable.", e)
    }
  }

  private fun requireDepth(depth: Int) {
    try {
      BundledZkey.requireSupportedDepth(depth)
    } catch (e: BundledZkey.ZkeyException) {
      throw CodedException("UnsupportedDepth", e.message ?: "Unsupported Merkle tree depth.", e)
    }
  }

  override fun definition() = ModuleDefinition {
    Name("Proof")

    AsyncFunction("generateSemaphoreProof") {
      privateKey: ByteArray,
      members: List<List<Int>>,
      message: String,
      scope: String,
      treeDepth: Int
    ->
      requireDepth(treeDepth)
      prepareProver()
      try {
        val identity = Identity(privateKey)
        val membersData = members.map { member -> member.map { it.toByte() }.toByteArray() }
        val group = Group(members = membersData)
        return@AsyncFunction generateSemaphoreProof(
          identity = identity,
          group = group,
          message = message,
          scope = scope,
          merkleTreeDepth = treeDepth.toUShort()
        )
      } catch (e: ProofException) {
        throw CodedException("ProofGenerationError", "Proof generation failed: ${e.message}", e)
      } catch (e: Exception) {
        throw CodedException("ProofGenerationError", "Unexpected error generating proof: ${e.message}", e)
      }
    }

    AsyncFunction("verifySemaphoreProof") { proof: String ->
      // semaphore-rs verify_proof loads the zkey for the depth declared inside the proof.
      requireDepth(BundledZkey.depthOf(proof))
      prepareProver()
      try {
        return@AsyncFunction verifySemaphoreProof(proof)
      } catch (e: ProofException) {
        throw CodedException("ProofVerificationError", "Failed to verify proof: ${e.message}", e)
      } catch (e: Exception) {
        throw CodedException("ProofVerificationError", "Unexpected error verifying proof: ${e.message}", e)
      }
    }
  }
}
