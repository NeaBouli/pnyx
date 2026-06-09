package expo.modules.semaphore

import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition
import expo.modules.kotlin.exception.CodedException
import uniffi.mopro.*

class ProofModule : Module() {

  override fun definition() = ModuleDefinition {
    Name("Proof")

    AsyncFunction("generateSemaphoreProof") { 
      privateKey: ByteArray, 
      members: List<List<Int>>, 
      message: String, 
      scope: String, 
      treeDepth: Int 
    ->
      try {
        // Create Identity from private key
        val identity = Identity(privateKey)
        
        // Create Group from members
        val membersData = members.map { member -> member.map { it.toByte() }.toByteArray() }
        val group = Group(members = membersData)
        
        // Generate semaphore proof with retry logic
        var proof: String? = null
        var lastException: Exception? = null
        
        // Try up to 3 times with exponential backoff
        for (attempt in 1..3) {
          try {
            proof = generateSemaphoreProof(
              identity = identity,
              group = group,
              message = message,
              scope = scope,
              merkleTreeDepth = treeDepth.toUShort()
            )
            break // Success, exit retry loop
          } catch (e: ProofException) {
            lastException = e
            if (e.message?.contains("dns error") == true || e.message?.contains("network") == true) {
              // Network error, wait before retry
              if (attempt < 3) {
                Thread.sleep(1000L * attempt) // Exponential backoff: 1s, 2s
                continue
              }
            }
            // Non-network error or max attempts reached, throw immediately
            throw e
          }
        }
        
        if (proof == null) {
          throw lastException ?: Exception("Failed to generate proof after 3 attempts")
        }
        
        return@AsyncFunction proof
      } catch (e: ProofException) {
        val errorMessage = when {
          e.message?.contains("dns error") == true -> "Network error: Unable to download required files. Please check your internet connection."
          e.message?.contains("zkey") == true -> "Proof generation error: Unable to access required cryptographic files."
          else -> "Proof generation failed: ${e.message}"
        }
        throw CodedException("ProofGenerationError", errorMessage, e)
      } catch (e: Exception) {
        throw CodedException("ProofGenerationError", "Unexpected error generating proof: ${e.message}", e)
      }
    }

    AsyncFunction("verifySemaphoreProof") { proof: String ->
      try {
        val isValid = verifySemaphoreProof(proof)
        return@AsyncFunction isValid
      } catch (e: ProofException) {
        throw CodedException("ProofVerificationError", "Failed to verify proof: ${e.message}", e)
      } catch (e: Exception) {
        throw CodedException("ProofVerificationError", "Unexpected error verifying proof: ${e.message}", e)
      }
    }
  }
} 